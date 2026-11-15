# Slopoly: notes for Claude

Slopoly is a CLI (`slopoly`, Python, installed with uv) and an agent skill that generate low-poly 3D game assets in
packs. This repository is both the plugin marketplace (`.claude-plugin/marketplace.json`, plugin in `plugin/`) and the
CLI source (`src/slopoly/`). The CLI drives the user's own ComfyUI (HTTP API) and Blender (background subprocess), and
keeps everything as plain files in a `slopoly/` workspace inside the user's repository. Planning lives in `openspec/`.

## Rules

- **Minimal code.** Prefer abstraction and reuse over new code. If a popular, maintained library does the job, use
  it (typer, pydantic, httpx, platformdirs, pywebview, manifold3d, ...). No obscure or unmaintained packages.
- **The repo is public.** Never commit host paths, user names or tokens, including in specs and docs. Use
  placeholders such as `<models-dir>`. Machine values live in the user's slopoly config folder.
- **Host dependencies.** The app needs only uv, Blender (5.0+) and a reachable ComfyUI. Code in
  `src/slopoly/blender/slopoly_model/` runs inside Blender's Python. Outside Blender it may import only its pure
  modules (`palette`, `glb`).
- **The skill is agent-neutral.** `plugin/skills/slopoly/` must work in any agent that reads files, runs shell
  commands and views images. Name CLI commands, never agent-specific tools.
- **Versions.** Keep `pyproject.toml`, `plugin/.claude-plugin/plugin.json`, `.claude-plugin/marketplace.json` and the
  version in `SKILL.md` equal (`tests/test_versions.py` checks this).
- **ComfyUI workflows** are built only with the `comfy` CLI, never through the ComfyUI GUI (see `comfyui/README.md`).
  Start from templates. Workflow files are API format, with inputs as nodes titled `in:<name>` and outputs as save
  nodes titled `out:<name>`.
- Only one ComfyUI may use the GPU at a time.

## Commands

```sh
uv run slopoly --help
uv run pytest                        # host tests; Blender-backed ones skip when Blender or its libraries are missing
uv run slopoly dev test-blender      # tests_blender/ inside Blender (installs pytest into the managed libraries)
uv run slopoly doctor                # environment check
uv tool install --force .            # install this checkout's CLI on the PATH
```
