# Proposal

## Why

Slopoly is a heavyweight local service today. Running it means Docker, the NVIDIA container toolkit, .NET, Aspire,
RabbitMQ and a SQLite database, plus its own bundled ComfyUI and Blender and a Claude Code agent tied to one
subscription. People who already have ComfyUI, Blender and a coding agent of their choice can't simply add Slopoly to
their own project. This change turns Slopoly into a CLI and an agent skill that work on plain files inside the user's
repository and use the ComfyUI and Blender the user already has.

## What Changes

- **BREAKING** Remove the Aspire stack: `Slopoly.AppHost`, `Slopoly.ApiService`, `Slopoly.Web`, `Slopoly.Contracts`,
  `Slopoly.ServiceDefaults`, `Slopoly.Tests`, the RabbitMQ setup, the worker containers (`containers/*`) and the shared
  worker library (`workers/`). The Blazor studio UI, the chats, the HTTP API and the MCP tool surface go with them.
  Existing SQLite data is not migrated.
- **BREAKING** Replace the database with a workspace of plain files (YAML, Markdown, PNG, Python programs, GLB and
  .blend builds) in a `slopoly/` folder inside the user's repository. Each pack is a folder there, for example
  `slopoly/my-cool-gnome-pack/`. Slopoly never runs git; the user commits what they want. Creating a pack writes a
  `.gitignore` that keeps the sources but ignores job scratch files and the binaries of builds that are not current.
- Add the `slopoly` CLI, a Python package installed with `uv tool install` from this repository. It scaffolds packs,
  assets, variants and scenes, validates workspace files, generates images, builds, validates and exports models,
  edits palettes and manages jobs. Every command prints machine-readable results (paths and numbers, never image
  data).
- Run generation on the user's existing ComfyUI over its HTTP API, using the workflow files shipped with the CLI.
  Run builds in the user's Blender as a background subprocess.
- Add `slopoly doctor`. It checks that ComfyUI is reachable and has the nodes and models the workflows need, that
  Blender is found with the libraries the build needs, and how the machine is configured. When the ComfyUI models
  folder is known, `slopoly doctor --fetch` downloads missing models into it.
- Run every slow or interactive operation as a detached job with a job file. The agent starts the job, gets an id,
  and calls `slopoly wait <id>` as often as it needs.
- Add native windows (pywebview, with a browser fallback). `slopoly pick` lets the user pick images (the rest is rejected) and
  answer the agent's choices as a detached job. `slopoly view` shows a build or scene in a three.js viewer with the
  existing overlays and the build comparison.
- **BREAKING** Replace the embedded Claude Code agent with an agent-neutral skill. This repository is a plugin
  marketplace that Claude Code, GitHub Copilot and other agents that support plugin marketplaces and skills can add.
  It ships one `slopoly` skill with reference files (the modelling API, the workflow and the knowledge notes) that
  drives the CLI. No Claude subscription token or Claude Code SDK is used.
- Machine-specific settings (ComfyUI URL, ComfyUI models folder, Blender path) live in the user's config directory,
  never in the workspace or this repository.

## Capabilities

### New Capabilities
- `slopoly-cli`: the `slopoly` command: installation, target addressing, machine-readable output and errors,
  scaffolding commands, file validation and status.
- `pack-workspace`: the file layout of a Slopoly workspace inside the user's repository, how it is found, what each
  file holds, and the generated `.gitignore`.
- `interaction-windows`: the pick window (detached user choices on images and options) and the view window (3D
  viewer and build comparison), including the browser fallback.
- `agent-plugin`: the plugin marketplace and the single `slopoly` skill with its reference files, and how the skill
  makes sure the matching CLI is installed.

### Modified Capabilities
- `local-runtime`: runs on the host with uv, the user's ComfyUI and Blender instead of Aspire and containers. Adds the
  environment check and model download, and machine settings move to the user config directory.
- `generation-jobs`: jobs become detached local processes recorded in job files, with wait, cancel, retry and orphan
  detection. The broker dispatch and redelivery requirements are removed.
- `design-agent`: the agent is whichever agent the user runs. It works through the CLI and the workspace files, and the
  subscription, chat, page-context and stop requirements are removed.
- `asset-packs`: packs, assets, concepts and builds are workspace files. Program history becomes numbered build
  snapshots, the file API is removed, and deletion works on folders.
- `asset-variants`: versions become per-variant build numbers with a current build. Variant creation and the second
  hero choice happen through the CLI and the pick window, and the database upgrade scenario is removed.
- `asset-viewer`: the viewer is the view window instead of the asset and scene pages, and overlay choices persist in
  the user's settings.
- `image-generation`: workflow files ship with the CLI and run on the user's ComfyUI.
- `knowledge-base`: shipped notes are skill reference files, and notes the agent writes go to the workspace. The UI
  editing requirement is removed.
- `part-modeling`: builds are opened in the view window, and the Blender download becomes `slopoly export --blend`.
- `scenes`: scenes are workspace files built with `slopoly scene build` and choose builds by number. The scene chat is
  removed.
- `studio-ui`: all requirements are removed. The build comparison moves to the view window.
- `surface-palette`: palette edits, recolouring and variant previews go through the CLI and the view window instead of
  the UI.
- `surface-shading`: shading settings live in `pack.yaml`, and defects are shown in the view window instead of the
  asset page.

## Impact

- **Code removed:** all .NET projects, `Slopoly.slnx`, `aspire.config.json`, `dotnet-tools.json`, `containers/`,
  `workers/`, the project-local Aspire skills under `.claude/skills/`, and `agent/` (its content moves into the skill).
- **Code moved and reused:** `geometry/slopoly_model` (runs inside Blender), `containers/comfyui/{views,colors,workflow,
  comfy_client}.py` (run in the CLI), `comfyui/workflows/*.json` (package data), `knowledge/**` and
  `agent/docs/slopoly_model.md` (skill references), and the three.js viewer logic from `Slopoly.Web` (view window).
- **New dependencies:** in the CLI, typer, pydantic, PyYAML, httpx, platformdirs, pywebview, numpy, Pillow and
  scikit-image. Inside Blender, Pillow, scikit-image and manifold3d, installed by `doctor` into a Slopoly-managed folder
  for the user's Blender version. three.js is vendored into the package.
- **Host requirements:** uv, Blender, and a reachable ComfyUI with the required nodes. Docker, .NET and Aspire are no
  longer needed.
- **Docs:** README, CLAUDE.md (host and test rules), `comfyui/README.md`, and the memory rule about running Python
  only in containers.
