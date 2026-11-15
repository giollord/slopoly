# Tasks

## 1. Marketplace spike and package skeleton

- [ ] 1.1 Spike: confirm which marketplace and plugin manifest paths GitHub Copilot CLI reads, and whether it accepts
  `.claude-plugin/marketplace.json`. Record the findings (commands tried, paths, versions) in this change's `notes.md`,
  and update design decision 9 if a second manifest is needed
- [ ] 1.2 Add `pyproject.toml` (package `slopoly`, src layout, console script `slopoly`, dependencies typer, pydantic,
  PyYAML, httpx, platformdirs, psutil, pywebview, numpy, Pillow, scikit-image; dev pytest and respx). Verify with
  `uv run slopoly --version`
- [ ] 1.3 Add `.claude-plugin/marketplace.json`, `plugin/.claude-plugin/plugin.json` and any manifest the spike found
  necessary, with a placeholder `plugin/skills/slopoly/SKILL.md`. Add a test that checks every manifest version equals
  the package version (`uv run pytest tests/test_versions.py`)

## 2. CLI core and workspace

- [ ] 2.1 Implement the JSON output helper and `SlopolyError` (code, message, hint) with exit statuses 1 and 2. Test
  that a raised error prints a JSON error and exits 1
- [ ] 2.2 Implement the pydantic models for `slopoly.yaml`, `pack.yaml`, `asset.yaml`, `variant.yaml`,
  `manifest.yaml`, `palette.yaml`, image sidecars, scene files, job files and note front matter, plus atomic YAML
  read and write. Test round trips and the validation error lists
- [ ] 2.3 Implement workspace discovery (walk up to `slopoly/slopoly.yaml`, `SLOPOLY_WORKSPACE`) and target addressing
  (`<pack>`, `<pack>/<asset>[:<variant>]`, `<pack>/scenes/<scene>`, image paths), with `no_workspace` and `not_found`
  errors. Test from nested folders and with unknown names
- [ ] 2.4 Implement `slopoly init`, `pack new`, `asset new`, `variant new` (empty, `--from`, `--hero`), `scene new`,
  variant rename and default, and `rm` (concept with views and masks, variant with the scene check, asset), with
  `exists` errors. Test that each scaffold writes the documented layout
- [ ] 2.5 Implement the generated pack `.gitignore` with its marked section, rewritten whenever a variant's current
  build changes. Test with a temporary git repository: `git status` shows only the current build's binaries, and user
  lines survive
- [ ] 2.6 Implement `slopoly check` (schemas, manifest parents, palette roles and slots, references, current builds,
  note names and front matter) and `slopoly status` (derived statuses, references, current builds, open jobs). Test
  against fixture workspaces, both valid and invalid
- [ ] 2.7 Implement machine settings (`slopoly config get|set`, environment overrides, platformdirs paths) and test
  that nothing is written inside the workspace

## 3. Blender builds

- [ ] 3.1 Move `geometry/slopoly_model` to `src/slopoly/blender/slopoly_model`, `geometry/samples` and
  `geometry/tests` to `tests_blender/`, and change `runner.py` to read workspace file paths instead of worker file
  ids. Keep its behaviour unchanged
- [ ] 3.2 Implement Blender discovery (setting, PATH, the usual install folders), the version check, the managed
  site-packages per Blender version, and the launcher script that sets `sys.path` and calls the runner. Test discovery
  with fake executables
- [ ] 3.3 Implement `slopoly build <target>`:
  - the next build folder, the program snapshot and `job.json` from the pack, asset, palette, reference views and
    masks;
  - the Blender subprocess with a timeout, and the report read back;
  - `current` updated only on success;
  - JSON result with the scores, paths, validation and shading counts.

  Implement `slopoly build use <target> <n>` too. Verify by building `samples/cart.py` into a test workspace
- [ ] 3.4 Implement `slopoly dev test-blender` (pytest inside Blender with the managed libraries) and run the moved
  geometry tests green with it, including the docs test over the skill's knowledge notes
- [ ] 3.5 Implement the palette commands (`palette add|set|rm|variant new|render`): stable slot assignment, used-entry
  refusal, and texture re-rendering that refreshes the current builds' GLBs through `glb.py` without Blender. Test
  that slots don't move and that a used entry can't be deleted
- [ ] 3.6 Implement `slopoly scene build [--current]` with `scene.py`, choosing current or numbered builds, and the
  `not built` and `version without a build` errors. Test it with two cart builds
- [ ] 3.7 Implement `slopoly export <target> --to <dir> [--build n] [--blend]` (GLB, variant textures, Blender file
  with relative palette paths, and the missing-Blender-file error). Test the exported file set

## 4. Jobs and ComfyUI generation

- [ ] 4.1 Implement the detached job runner: the job file, the detached spawn per OS, the log, progress, atomic
  outputs, orphan detection through pid and start time, and the "pack folder gone" failure. Add `slopoly jobs`,
  `wait [--timeout]`, `cancel` and `retry`. Test with a no-op job kind: start, wait pending, finish, cancel, retry,
  and an orphan after killing the process
- [ ] 4.2 Move `comfy_client.py`, `workflow.py`, `views.py` and `colors.py` into `src/slopoly/comfy/`, and the API
  workflows into package data. Switch them to HTTP upload and download with no shared files, and keep the existing
  ComfyUI tests (respx fixtures) passing under `uv run pytest`
- [ ] 4.3 Implement `slopoly gen anchor`, `gen hero` (picked-anchor check, variant target, count 1 to 4, seeds),
  `gen revise` (fresh seed, change text, concept as first reference), `gen views` (picked-hero check, front yaw,
  replacement of old views) and `segment` (parts list, masks, bounds, areas, colours, missing parts) as jobs that write
  images and sidecars. Test each against the fake ComfyUI
- [ ] 4.4 Map ComfyUI failures to `missing_model` and `missing_node` codes, with hints naming `slopoly doctor`, and test
  them with the fake ComfyUI's error responses

## 5. Doctor and model download

- [ ] 5.1 Add `src/slopoly/comfy/models.yaml` from the table in `comfyui/README.md` (file, subfolder, URL, size,
  licence, workflows)
- [ ] 5.2 Implement `slopoly doctor`. It checks ComfyUI reachability, nodes derived from the workflows' `class_type`s
  against `/object_info`, models against `/models/<folder>`, Blender and its version, and the managed libraries, and
  prints a fix for each failure. Test with a fake ComfyUI and a fake Blender
- [ ] 5.3 Implement `slopoly doctor --fetch`:
  - resumable model downloads into the configured models folder (`.part`, then rename), announcing the total size
    first;
  - when the folder is unknown, a list of the models instead of downloads;
  - installing the pinned Blender libraries into the managed folder with Blender's Python.

  Test the resume and the unknown-folder output with a local HTTP fixture

## 6. Pick and view windows

- [ ] 6.1 Implement the window server: loopback with a random port and token, safe workspace file serving, and the
  state, choice and prefs endpoints. Implement the job wrapper that opens pywebview, falls back to the browser, and
  reports its URL. Test the API and path safety without opening a window
- [ ] 6.2 Implement `pick.html` and `slopoly pick`: anchors, heroes or image paths, an optional question with options,
  a count limit, a note, the confirm and cancel paths, the reference choice (replace or new variant with a name), and
  the non-interactive `slopoly pick --set <image> picked|rejected [--replace|--new-variant <name>]`. Test that a posted
  choice updates the sidecars and finishes the job, and that a CLI pick without the reference choice is refused
- [ ] 6.3 Port the three.js viewer from `Slopoly.Web` to `view.html`, with three.js vendored: orbit and reset,
  wireframe, grid, axes, normals, the shade toggle, the palette variant switch, persisted overlays, and for a build the
  comparison images with scores, the validation summary and the shading defect counts. Implement `slopoly view` with
  live reload when `current` changes. Check it by opening the sample cart build

## 7. Skill and references

- [ ] 7.1 Write `plugin/skills/slopoly/SKILL.md`: bootstrap (version check, `uv tool install`, doctor), the workflow
  steps with the commands for each, the rules (pick before modelling, no rejected images, images opened only on
  purpose, score threshold, usage-named palette roles), and which reference to read at each step. Check that it states
  the package version, through the version test
- [ ] 7.2 Move `agent/docs/slopoly_model.md` to `references/modelling-api.md` and `knowledge/**` to
  `references/knowledge/`, and write `workflow.md`, `palette-and-shading.md` and `comfyui-setup.md` from
  `agent/CLAUDE.md` and `comfyui/README.md`, in CLI terms without agent-specific tool names. Check with
  `slopoly dev test-blender` (the docs test) and a grep for "MCP" and "tool" wording
- [ ] 7.3 Install the plugin from a local checkout in Claude Code, and in GitHub Copilot CLI as the spike found, and
  confirm that the skill loads and its bootstrap installs the CLI. Record the results in `notes.md`

## 8. Remove the Aspire stack and update docs

- [ ] 8.1 Delete `Slopoly.AppHost`, `Slopoly.ApiService`, `Slopoly.Web`, `Slopoly.Contracts`,
  `Slopoly.ServiceDefaults`, `Slopoly.Tests`, `Slopoly.slnx`, `aspire.config.json`, `dotnet-tools.json`,
  `containers/`, `workers/`, `agent/`, `geometry/` (now moved), `knowledge/` (now moved) and the Aspire skills under
  `.claude/skills/`. Verify that `git grep -i -E "aspire|rabbitmq|dotnet"` finds only historical specs and archived
  changes
- [ ] 8.2 Rewrite the README: install (uv, Blender, ComfyUI), adding the marketplace in each agent, configuration,
  doctor and fetch, the workspace layout and `.gitignore`, the trust note about running programs in Blender, and
  tests. Update CLAUDE.md's host-dependency, test-command and Commands sections, and `comfyui/README.md`'s paths.
  Verify that the documented commands run as written
- [ ] 8.3 Check the repository for host paths, user names and tokens (`git grep` for drive letters, home folders and
  token patterns) and verify that only placeholders appear

## 9. End-to-end check

- [ ] 9.1 Run the cart scenario through an agent with the installed plugin on the user's ComfyUI and Blender: pack,
  anchors, pick, cart heroes, pick, views, segmentation, manifest, program, the build loop to validation, palette,
  view window, export. Record the outcome, timings and blockers in `notes.md`
- [ ] 9.2 Run `uv run pytest` and `uv run slopoly dev test-blender` green, and run `openspec validate
  slopoly-cli-agent-plugin --strict`

## Workflow follow-up

- After archiving, update the Purpose sections of `local-runtime`, `generation-jobs`, `design-agent` and
  `studio-ui` (now without requirements; delete that spec if nothing replaces it) in `openspec/specs/`.
