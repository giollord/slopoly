# Design

## Context

See proposal.md (Why) for the motivation. The reusable logic is already in Python and doesn't depend on the service
stack:

- `geometry/slopoly_model/` (about 2k lines) runs part programs inside Blender (`bpy`, `bmesh`, `mathutils`). It also
  needs numpy, Pillow, scikit-image and manifold3d. `runner.py` already works as a subprocess: it reads
  `job.json` and writes `report.json`, `model.glb`, `model.blend` and the render and comparison PNGs.
- `containers/comfyui/` has the ComfyUI HTTP client, the workflow input filling (`in:<name>` and `out:<name>` nodes),
  front-direction detection and view picking from the splat turntables (`views.py`), and colour measurement
  (`colors.py`).
- `comfyui/workflows/*.json` are API-format workflows. `comfyui/README.md` lists the required models with their URLs.
- `knowledge/**`, `agent/CLAUDE.md` and `agent/docs/slopoly_model.md` are the agent's instructions and references.
- `Slopoly.Web` has the three.js viewer, with its wireframe, grid, axes, normals, shade toggle and palette swap.

Everything else (.NET API, Blazor, EF Core, RabbitMQ, the worker library, the agent worker and the Docker images)
exists only to connect these pieces, and is removed.

## Goals / Non-Goals

**Goals:**
- One repository is both the plugin marketplace and the source of an installable Python CLI.
- The CLI works with an existing ComfyUI (local or on the network) and an existing Blender, without containers.
- All state is in plain files that a person can read, diff and commit.
- Reuse the existing geometry, ComfyUI and viewer code with as few changes as possible.

**Non-Goals:**
- Migrating existing SQLite data.
- A long-running Slopoly server or daemon. Windows and jobs are short-lived processes.
- Installing ComfyUI or its custom nodes. Doctor reports them and downloads models only.
- Installing Blender. Doctor finds it or says where to get it.
- Agent-specific features such as hooks, MCP servers or slash commands.

## Decisions

### 1. Repository layout

```
.claude-plugin/marketplace.json      marketplace (plus any other agent's manifest path, see decision 9)
plugin/
  .claude-plugin/plugin.json         plugin "slopoly", version = package version
  skills/slopoly/SKILL.md
  skills/slopoly/references/         modelling-api.md, workflow.md, palette-and-shading.md, comfyui-setup.md,
                                     knowledge/techniques/*.md, knowledge/objects/*.md
pyproject.toml                       package "slopoly", console script "slopoly"
src/slopoly/
  cli.py                             typer app; one module per command group
  workspace.py, models.py            file discovery, pydantic schemas for every YAML file
  jobs.py                            detached job runner, job files, wait/cancel/retry
  comfy/                             client.py, workflow.py, views.py, colors.py (moved from containers/comfyui)
    workflows/*.json, models.yaml    package data (moved from comfyui/workflows, model list from comfyui/README.md)
  blender/                           launcher.py (runs on the host), slopoly_model/ (runs inside Blender), libs.py
  windows/                           server.py, pick.html, view.html, vendor/three/ (package data)
tests/                               host tests (uv run pytest)
tests_blender/                       geometry tests, run inside Blender
comfyui/                             developer sources: UI-format graphs, recipes, README (kept)
```

- **Why `plugin/` is a subfolder:** the plugin directory is copied into the agent's plugin cache. A subfolder keeps
  the Python source, the tests and the specs out of it.
- **Why the knowledge notes live in the skill and not in the package:** they are the agent's reading material, and the
  CLI never needs them. The Blender test suite runs every note's code samples from their skill paths, as
  `test_docs.py` does today.

### 2. CLI stack: typer, pydantic and PyYAML

- **typer** gives subcommands, help and typed options with little code.
- **pydantic** models are the schemas for `pack.yaml`, `asset.yaml`, `variant.yaml`, `manifest.yaml`, `palette.yaml`,
  image sidecars, scenes and job files. They also produce the error lists that `slopoly check` prints.
- One output helper prints a model or dict as JSON. Errors are a `SlopolyError(code, message, hint)` exception that
  the app catches and prints as JSON with exit status 1. Status 2 means the user's program failed during a build.
- Alternatives: click (more boilerplate) and argparse (no help for nested groups). jsonschema was also considered,
  but pydantic already gives typed access to the same files.

### 3. Workspace format

```
slopoly/
  slopoly.yaml                  {format: 1}
  knowledge/{techniques,objects}/*.md     notes the agent writes
  <pack>/
    pack.yaml                   name, budget, shading {mode, hard_edge_angle, shade_strength}
    style.md                    instructions + style text (two headed sections)
    palette.yaml                entries [{role, kind, slot, color, color2?, axis?}], variants {name: {role: colors}}
    palette/                    rendered textures (main.png, <variant>.png)
    style/                      reference images (+ sidecars)
    anchors/                    anchor_001.png + anchor_001.yaml ...; rejected/ (unpicked, git-ignored)
    assets/<asset>/
      asset.yaml                description, budget?, default_variant
      heroes/hero_001.png + .yaml; rejected/
      views/<hero>/{front,side,top,back}.png, *_mask.png, views.yaml (bounds, front_yaw, front source); rejected/
      masks/<hero>/<part>_<view>.png, masks.yaml (bounds, area, colours, missing); rejected/
      variants/<variant>/
        variant.yaml            reference (a hero file name in heroes/), current (build number)
        manifest.yaml
        program.py
        builds/0001/            program.py, report.json, model.glb, model.blend, palette.png, render_*.png, compare_*.png
        builds/rejected/0002/   a build that failed with a program error (git-ignored)
    scenes/<scene>.yaml, scenes/<scene>/builds/0001/...
    jobs/<id>.yaml, jobs/<id>.log
    .gitignore
```

- **Statuses are derived from the files and never stored:** an asset with a manifest is "manifest", one with a build
  is "built", one whose current build is validated is "validated". There is nothing to keep in sync.
- **Sidecar YAML per image, not one index file per folder:** concurrent jobs and the pick window never write the same
  file, and git diffs stay local to the changed image.
- **File writes are atomic:** each write goes to a temporary file in the same folder, then `os.replace`. Readers never
  see half-written YAML.
- **Build numbers** are the highest existing `builds/NNNN` (including `builds/rejected/`) plus one.
- **Heroes belong to the asset, variants point at them:** several heroes picked at once become several variants without
  moving files, and replacing a reference only rejects the old hero when no other variant uses it.
- **Not picked means rejected:** the pick window has only a pick toggle. Unpicked images move to `rejected/`, which the
  generated `.gitignore` ignores, so the folders the agent reads hold only live images.
- **The program file:** `program.py` is the editable working copy, and each build snapshots it. `slopoly build use <n>`
  copies the snapshot back and sets `current`. A failed build still gets a folder (with the program and an error
  report), so the history of attempts is visible. `current` only moves to a build that succeeded.
- **The `.gitignore`** has a marked section that `pack new` writes and that each change of `current` rewrites. It
  ignores `jobs/` and `builds/*/{model.glb,model.blend,palette.png,render_*,compare_*}`, then un-ignores those same
  paths for each variant's current build. Lines outside the markers are kept.
- **Alternative considered:** one SQLite file in the workspace. It was rejected because the user asked for files, and
  SQLite doesn't diff, merge or edit by hand.

### 4. Machine settings: platformdirs

- `slopoly config set comfyui.url|comfyui.models_dir|blender.path <value>` writes `config.yaml` in
  `platformdirs.user_config_dir("slopoly")`. Each setting can also be given as an environment variable
  (`SLOPOLY_COMFYUI_URL`, ...).
- Viewer overlay preferences go in the same folder.
- The Blender libraries go in `user_data_dir("slopoly")/blender/<blender-version>/site-packages`.
- Blender discovery order: the `blender.path` setting, then `blender` on the PATH, then the usual install folders per
  OS (the newest supported version).

### 5. Blender as a subprocess, with Slopoly-managed libraries

- **How a build runs:**
  1. `slopoly build` writes `job.json` into the new build folder.
  2. It runs `blender --background --factory-startup --python-exit-code 3 --python <launcher> -- <build-dir>`, with a
     timeout. The launcher prepends the managed site-packages and the package's `blender/` folder to `sys.path`, then
     calls `slopoly_model.runner.main`.
  3. The runner is unchanged apart from paths: masks and views become file paths in the workspace.
- **Libraries:** `doctor --fetch` runs Blender's bundled Python (`sys.executable` as reported by Blender) with
  `-m pip install --target <managed dir>` for Pillow, scikit-image and manifold3d. The versions are pinned in
  `blender/requirements.txt`. Blender's install folder is never written.
- **Supported Blender:** 5.x, matching the `bpy==5.3.0` the geometry tests use today. Doctor reads the version from
  `blender --version`.
- **Alternatives considered:**
  - The `bpy` wheel in the CLI env: it pins one Python minor version and is a big download (decided against during
    explore).
  - Doing all image work in the host process and only meshes in Blender: it would split `runner.py` and
    `render.py`, so it means more code for the same result.
- **Builds are synchronous**, not detached jobs. A build takes seconds to a couple of minutes, and the agent needs the
  result right away. The default timeout is 300 s (`--timeout`). Scene builds and palette refreshes, which re-embed
  textures in GLBs, run in the CLI process with the existing `glb.py` and `scene.py` code. Neither needs Blender.

### 6. ComfyUI over HTTP

- The client from `containers/comfyui/comfy_client.py` is kept on httpx, with these calls:
  - `POST /upload/image` for references and heroes
  - `POST /prompt` with the filled API-format workflow
  - `GET /history/<id>` (polled) and `/ws` for progress where available
  - `GET /view` to download outputs
  - `POST /interrupt` or `POST /queue {delete}` for cancel
- Nothing depends on a shared filesystem, so a ComfyUI on another machine works.
- The view picking (`views.py`) and colour measurement (`colors.py`) run in the job process on the host. This is why
  the CLI depends on numpy, Pillow and scikit-image.
- **`models.yaml`** lists each required model: file, subfolder, URL, size, licence, and the workflows that use it.
  `doctor` checks it against `GET /models/<folder>`, and `--fetch` downloads into
  `<models_dir>/<subfolder>/<file>.part`, then renames the file. HTTP Range requests resume a partial download. The
  sizes total about 37 GB, and doctor says so before starting.
- **Required nodes are derived, not listed:** doctor collects every `class_type` in the shipped workflows and checks
  them against `GET /object_info`. A workflow change can't leave the node list out of date.
- **One GPU job at a time:** ComfyUI's queue already runs prompts one at a time, so Slopoly adds no lock of its own.

### 7. Detached jobs

- **Starting a job:** `slopoly gen ...` validates its inputs, writes `jobs/<id>.yaml` (state queued, kind, target,
  inputs), and starts the job process detached. On Windows that means `DETACHED_PROCESS | CREATE_NEW_PROCESS_GROUP`.
  On POSIX it means `start_new_session=True`. The job process is
  `python -m slopoly _job run <path>`, using the same interpreter. The command then prints `{"job": id, "state": "queued"}`.
- **What the job process does:**
  1. Records its pid and start time.
  2. Sets the state to running and updates progress.
  3. Writes its outputs into the workspace.
  4. Sets succeeded with a result, or failed with code and message. stdout and stderr go to `jobs/<id>.log`.
- **`wait`** polls the job file every 0.5 s until the job finishes or the timeout passes. The default timeout is
  540 s, which stays under common agent shell limits of about 10 minutes. On timeout it returns `pending` and the
  progress. It writes nothing.
- **Orphans:** if the state is queued or running but no process with the recorded pid and start time exists, the job
  is reported (and written) as failed with code `orphaned`. psutil checks the process, and the start time guards
  against a reused pid.
- **Cancel** writes `cancel_requested` and terminates the process. The job process's handler, or the canceller when
  the process is already gone, interrupts or deletes the ComfyUI prompt and sets the state to cancelled.
- **Outputs are written only on success**, to a temporary name first and then moved. A cancelled or failed job
  attaches nothing. A job whose pack folder has disappeared fails without writing.
- **Alternatives considered:**
  - A local daemon with a queue: one more process to manage, for no gain over ComfyUI's own queue.
  - Synchronous commands with long timeouts: they break on agent shell limits (decided against during explore).

### 8. Pick and view windows: pywebview with a stdlib HTTP server

- **One local server, two pages:** a pick or view job starts a `ThreadingHTTPServer` on `127.0.0.1:<random port>`
  that serves `pick.html` or `view.html`, a small JSON API (`GET /api/state`, `POST /api/choice`) and workspace
  files.
- **Path safety:** files are served only from under the workspace, and every request path is resolved and checked.
  A random token in the URL keeps other local pages from posting choices.
- **pywebview** opens a native window on that URL: WebView2 on Windows, WebKit on macOS, GTK or Qt on Linux. When
  `webview.start` raises because no backend is available, the job opens the URL with `webbrowser.open` and stays alive
  until the choice is posted or the job is cancelled.
- **Pick:** `POST /api/choice` writes the sidecars (and, for "New variant", creates the variant), records the result,
  and closes the window. Closing the window without confirming ends the job as cancelled.
- **View:** the job stays open until the window closes. It polls `variant.yaml` and reloads when `current` changes.
- **The viewer port:** the three.js code from `Slopoly.Web`'s viewer is ported to a plain ES module page. three.js is
  vendored (MIT) so it works offline and avoids CDN version drift. Overlay choices are saved through
  `POST /api/prefs` into the user config folder.
- **Alternatives considered:** MAUI (adds .NET back and has no Linux desktop), and Tk or Qt widgets (no three.js, and a
  second UI toolkit).

### 9. Marketplace manifests

- **Claude Code:** `.claude-plugin/marketplace.json` lists the plugin `slopoly` with `source: "./plugin"`, and
  `plugin/.claude-plugin/plugin.json` names the skill.
- **GitHub Copilot CLI:** its plugin marketplace support reads a marketplace manifest from the repository, and the
  first task is a spike to confirm the paths it accepts. If it reads `.claude-plugin/marketplace.json`, no second file
  is needed. Otherwise a second manifest at the path Copilot reads points to the same `./plugin` folder.
- **Other agents** that read Agent Skills folders (`SKILL.md` with name and description front matter) can use
  `plugin/skills/slopoly` directly, which the README documents.
- **Versioning:** one version string lives in `pyproject.toml`. A test checks that `plugin.json`, the marketplace
  entry and the version the SKILL.md requires all match it.

### 10. The skill

- **SKILL.md** has front matter (name `slopoly`, a description that triggers on low-poly or game asset requests) and
  covers:
  1. bootstrap: the version check, `uv tool install git+<repo-url>@v<version>` and doctor;
  2. the workflow: brief, then style and anchors, then pick, then asset, then heroes, then pick, then views, then
     segmentation, then manifest, then program, then the build and compare loop, then palette, then export;
  3. the rules: ask through pick before modelling, never use rejected images, open images only on purpose, stop at
     the score threshold, name palette roles by usage;
  4. a command cheat sheet, and which reference to read at each step.
- **References** are the current `agent/docs/slopoly_model.md` (renamed `modelling-api.md`), the relevant parts of
  `agent/CLAUDE.md`, and the knowledge notes. All agent-specific wording ("tool", "MCP") becomes CLI commands.

### 11. Tests without containers

- **Host tests** run with `uv run pytest`: CLI commands on a temporary workspace, schemas, `.gitignore` upkeep, jobs
  (with a fake ComfyUI through respx, reusing the existing fixtures), doctor with a fake `object_info` and models API,
  window server API calls (without opening a window), and version consistency.
- **Blender tests** run with `uv run slopoly dev test-blender`. It runs pytest inside the found Blender, with the managed
  libraries plus pytest. The existing `geometry/tests` move unchanged.
- CLAUDE.md's "All Python runs in containers" rule is replaced by these two commands.

## Risks / Trade-offs

- **[Risk] Copilot CLI's marketplace format differs or changes.** → The spike comes first. The manifests are only a
  few lines, so a second file costs little, and the skill folder itself follows the shared standard.
- **[Risk] Blender's bundled Python can't build a pinned library on some OS.** → Pin versions that ship wheels for
  Blender 5.x's Python on Windows, macOS and Linux. Doctor reports pip's error with the Blender version.
- **[Risk] The user's ComfyUI lacks nodes (Idol, SAM 3.1, RenderSplat) or runs an older version.** → Doctor names
  each missing class and the workflow that needs it, and `comfyui-setup.md` explains how to update or install them.
  Jobs fail with `missing_node` and never hang.
- **[Risk] Detached processes behave differently per OS:** Windows consoles, and macOS app nap for GUI windows. →
  Integration tests start, wait on and cancel a real detached no-op job on the developer's OS. Windows and macOS
  notes go in the README.
- **[Risk] pywebview has no backend on minimal Linux.** → The browser fallback is part of the spec, and the result
  includes the URL.
- **[Trade-off] Builds run arbitrary agent-written Python in the user's Blender with the user's rights.** Before, the
  program ran in a container. → The README says so. The trust level is the same as letting the agent edit and run
  code in the repository, which it already does.
- **[Trade-off] No migration of existing SQLite data.** → The last commit with the Aspire stack stays in history for
  anyone who needs the old data.
- **[Trade-off] Binaries in the user's repository.** → Only the current build's binaries are left un-ignored by the
  generated `.gitignore`.

## Migration Plan

1. Build the new CLI next to the old stack until the cart end-to-end scenario passes through an agent with the
   plugin. The old stack keeps working until then.
2. Remove the .NET projects, containers, workers, Aspire config and Aspire skills, and update README, CLAUDE.md and
   `comfyui/README.md`.
3. Rollback: revert the removal commit. The old stack has no state shared with the new workspace.

## Open Questions

- The exact Pillow, scikit-image and manifold3d pins that have wheels for the Python of the oldest supported
  Blender 5.x. This is settled while implementing the Blender libraries task, and doesn't change the approach.
