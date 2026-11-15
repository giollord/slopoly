# Slopoly

Slopoly makes low-poly 3D game assets in style-consistent packs, driven by your coding agent. It works in three steps:

1. **Concept images.** ComfyUI makes style anchors, then hero images of each asset, then orthographic views of each
   hero (from a 3D splat).
2. **Part programs.** Your agent writes Python programs that build each asset from named parts.
3. **Builds.** Blender builds a program into validated multi-part geometry, coloured through a shared palette
   texture, scored against the views, and exported as GLB and .blend.

Slopoly is:

- **a CLI**, `slopoly`;
- **an agent skill**, shipped from this repository as a plugin marketplace for Claude Code, GitHub Copilot CLI and
  other agents with plugin marketplaces or Agent Skills.

Everything lives as plain files in a `slopoly/` folder in your own repository.

## Requirements

- [uv](https://docs.astral.sh/uv/), which installs the CLI and its Python.
- [Blender](https://www.blender.org/download/) 5.0 or newer. It is found automatically in the usual install
  folders, or set with `slopoly config set blender.path <path>`.
- A [ComfyUI](https://github.com/comfyanonymous/ComfyUI) you can reach over HTTP. It has to be a recent version
  (tested with 0.45.3), running on an NVIDIA GPU (designed for 12 GB of VRAM). It can run on another machine.
- A coding agent with plugin or skill support (Claude Code, GitHub Copilot CLI, ...).

## Install

Add the marketplace and install the plugin in your agent:

```sh
# Claude Code
/plugin marketplace add giollord/slopoly
/plugin install slopoly@slopoly

# GitHub Copilot CLI
copilot plugin marketplace add giollord/slopoly
copilot plugin install slopoly@slopoly
```

Agents that read [Agent Skills](https://agentskills.io) folders can use `plugin/skills/slopoly/` directly.

The skill installs the matching CLI itself the first time it's used. To install it by hand:

```sh
uv tool install "git+https://github.com/giollord/slopoly@v0.1.0"
slopoly --version
```

## Configure

Machine settings are stored in your user config folder, never in a workspace or this repository:

```sh
slopoly config set comfyui.url http://127.0.0.1:8188           # default
slopoly config set comfyui.models_dir <models-dir>              # your ComfyUI's models folder (for --fetch)
slopoly config set blender.path <path to blender>               # only if it isn't found
slopoly config show
slopoly doctor            # checks ComfyUI (reachable, nodes, models), Blender (version, libraries) and settings
slopoly doctor --fetch    # downloads missing models (about 37 GB in all) and installs Blender's build libraries
```

`doctor --fetch` installs Pillow, scikit-image and manifold3d for Blender's own Python into a Slopoly-managed folder.
Blender's installation is not changed. The required models and their licences are listed in `comfyui/README.md`.

## Use

Ask your agent for assets, for example "make a low-poly gnome village pack: a wooden cart, a well and a mushroom
house". The skill takes it through these steps:

1. `slopoly init` creates the workspace.
2. Style anchors are generated, and you pick the ones you like.
3. Heroes of each asset are generated, and you pick one (or several: each becomes its own variant).
4. Views and part masks are made from the picked hero.
5. The agent writes the palette, the manifest and the part program.
6. The agent builds and compares with the views until the model looks right.

A small window (or a browser tab) opens whenever you need to choose, and `slopoly view <pack>/<asset>` opens a 3D
viewer with the build's comparison images.

Each pack is a folder:

```
slopoly/
  slopoly.yaml
  knowledge/                      notes the agent writes (techniques, objects)
  my-cool-gnome-pack/
    pack.yaml  style.md  palette.yaml  palette/  style/  anchors/  scenes/  jobs/  .gitignore
    assets/cart/
      asset.yaml
      heroes/  views/  masks/       concept images of the asset, and the views and part masks of picked ones
      variants/default/
        variant.yaml  manifest.yaml  program.py
        builds/0001/  program.py  report.json  model.glb  model.blend  render_*.png  compare_*.png
```

Slopoly never runs git, so commit what you want to keep. Each pack's generated `.gitignore` keeps the sources, every
build's program and report, and the current builds' models. It ignores job files, the binaries of older builds, and
the `rejected/` folders, where images you didn't pick and failed builds are set aside.
Lines you add outside its marked section are kept.

Export a build for your game with `slopoly export <pack>/<asset> --to <dir> [--blend]`. Run `slopoly --help` to see
every command.

**Trust:** a build runs the agent-written `program.py` in your Blender with your user rights. That is the same trust
you give an agent that edits and runs code in your repository.

## Develop

```sh
uv run slopoly --version                  # the CLI from this checkout
uv run pytest                             # host tests (Blender-backed tests skip without Blender)
uv run slopoly dev test-blender           # geometry tests inside your Blender
uv tool install --force .                 # put this checkout's CLI on the PATH
```

- **Workflows** are edited with the `comfy` CLI (see `comfyui/README.md`).
- **Planning** lives in `openspec/`.
- **Versions:** the version is in `pyproject.toml`, `plugin/.claude-plugin/plugin.json`,
  `.claude-plugin/marketplace.json` and the skill. A test keeps them equal. Tag releases `v<version>`, because the
  skill installs from that tag.
