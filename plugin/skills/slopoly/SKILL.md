---
name: slopoly
description: Make low-poly 3D game assets and asset packs (props, buildings, vehicles, characters, scenes) with the slopoly CLI, which drives ComfyUI concept images and Blender part programs. Use when the user wants game-ready low-poly models, a style-consistent asset pack, or to change, rebuild, recolour or export assets in a slopoly/ workspace.
---

# Slopoly

You turn a brief into low-poly 3D assets with the `slopoly` CLI. It makes style-consistent concept images on the
user's ComfyUI and builds Python part programs, which you write, into validated multi-part models in the user's Blender.
All content lives as plain files in a `slopoly/` folder in the user's repository.

Requires slopoly CLI version 0.2.2.

## Before the first command

1. Run `slopoly --version`. If the command is missing or prints another version, install this one:
   `uv tool install --force "git+https://github.com/giollord/slopoly@v0.2.2"` (uv: https://docs.astral.sh/uv/).
2. After installing, or when a command fails with a setup error, run `slopoly doctor`. It checks ComfyUI, its nodes
   and models, Blender and the build libraries, and gives a fix for each failure. `slopoly doctor --fetch` downloads
   missing models (when `comfyui.models_dir` is set) and installs the Blender libraries. Model downloads are large
   (tens of GB), so ask the user before fetching. Read `references/comfyui-setup.md` when ComfyUI needs nodes or
   settings.
3. With no workspace (`no_workspace` error), ask the user, then run `slopoly init` in the repository root.

## How the CLI works

- Every command prints one JSON document. Errors are JSON too, with `code`, `error` and usually a `hint` naming the
  fix. Paths in results are relative to the repository root.
- Targets: `<pack>`, `<pack>/<asset>`, `<pack>/<asset>:<variant>` (no variant means the asset's default) and
  `<pack>/scenes/<scene>`. Images are named by their path.
- Generation, views, segmentation and the pick, view and review windows are **detached jobs**. They return `{"job": <id>}` at once. Run
  `slopoly wait <id>` for the result. If it returns `"state": "pending"`, run it again; waiting has no side effects.
  Window commands also return the window's local `url`: give it to the user when no window appeared.
  `slopoly jobs` lists open jobs, `slopoly cancel <id>` and `slopoly retry <id>` do what they say.
- Builds (`slopoly build`) run in the foreground and return the report.
- `slopoly status [target]` shows what exists: assets, statuses, reference heroes, current builds and open jobs.
  Start there in a new session.
- `slopoly check` validates every file after you edit YAML by hand.

## Workflow

Follow `references/workflow.md` for the details of each step.

1. **Pack and style.** `slopoly pack new <pack>`. Write the brief into `style.md` (instructions and style text), and
   set the budget and shading in `pack.yaml` (`references/palette-and-shading.md`).
2. **Style anchors.** `slopoly gen anchor <pack> --prompt "<scene with several typical objects>" --count 3`, then
   `slopoly wait`. Then `slopoly pick <pack> --anchors` and wait for the user's choice.
3. **Asset and heroes.** `slopoly asset new <pack>/<asset> --description "..." --size <metres>`, stating the real
   size, and `--budget N` from the part count you expect. Then `slopoly gen hero <pack>/<asset> --count 3`, wait,
   then `slopoly pick <pack>/<asset> --heroes` and wait. Each picked hero becomes the reference of its own variant
   (the first one of the default variant); the rest is rejected. To replace a variant's reference instead, use
   `--for <variant>`.
4. **Views.** `slopoly gen views <pack>/<asset>` makes a rough 3D reference mesh of the reference hero and renders
   front, side, top and back views of it in metres, then wait. If the result says `"front": "assumed"`, ask the user
   whether the front view shows the front, and rerun with `--front-yaw` if not. `slopoly look <pack>/<asset> --from
   <direction>` renders close-ups of the reference mesh from any direction.
5. **Segmentation.** `slopoly segment <pack>/<asset> --parts "bed,wheel,axle,handle"`, then wait. The result has
   part masks with bounds, areas and measured colours, each part's 3D region in metres, and lists missing and
   implausible parts. Coarse names first for busy objects.
6. **Palette.** `slopoly palette add <pack> "<role>" "#rrggbb"`, adding `--to "#rrggbb"` for a gradient. Start from
   the measured colours and name roles by usage.
7. **Knowledge.** Search `references/knowledge/` and the workspace's `slopoly/knowledge/` for the asset's kind and
   its notable features, and read the matching notes.
8. **Manifest and program.** Write `manifest.yaml` with a shape plan (`shape`, `steps`, `checks`) for every part of a
   complex asset and every distinctive part, check the plans against `slopoly look` close-ups, then write
   `program.py` (`references/modelling-api.md`) and run `slopoly build <pack>/<asset>`.
9. **Iterate.** Fix failing validation first, then likeness: the silhouette scores, `detail` regions and
   `compare3d` regions. Stop at the bar or report what blocks you (`references/workflow.md`).
10. **Review.** When a build is worth showing, `slopoly review <pack>/<asset>` and wait: the user paints and comments
    on the reference beside the build. Work through the notes (the comment decides; part hits are hints), and set
    each with `slopoly note <target> <n> addressed --by <build> --reason "..."` or `wontfix`. Stop when no notes are
    open and every IoU drop since the review is explained.
11. **Show and export.** `slopoly view <pack>/<asset>` opens the 3D viewer for the user.
    `slopoly export <pack>/<asset> --to <dir> [--blend]` writes the GLB, the palette textures and optionally the
    Blender file.

## Rules

- **Ask through the pick window.** Never pick or reject images for the user. Before moving from concepts to
  modelling, the user must have picked the hero. Use `slopoly pick ... --question "..." --option A --option B` for
  other choices that are easier to answer with images in view.
- **Never use rejected images.** Whatever the user doesn't pick is moved to a `rejected/` folder (git-ignored).
- **Work from numbers.** Results give paths, bounds, areas, scores and colours. Open an image file only when the
  numbers can't answer a question, or for the comparison images of views below the bar.
- **Only edit agent-editable files:** `style.md`, `pack.yaml`, `asset.yaml`, `manifest.yaml`, `program.py`, scene
  files, palette variant colours, and notes in `slopoly/knowledge/`. Everything else goes through commands. Never
  edit build folders or image metadata by hand.
- **Never run git.** The user commits their own work.
- **Write files with your file-editing tools**, never with shell heredocs or `echo`: shells mangle backslashes, quotes
  and line breaks in Python and YAML.
- **Write a variant as one target**, `<pack>/<asset>:<variant>`, never as two arguments.
- **Palette roles are named by usage** ("wall base", "cart wood"). Use colour names ("leaf green") only for colours
  that stay the same in every palette. Model and score only with the main palette, and make palette variants only
  when asked.
- **Keep replies to the user short:** what you did, what you need from them, and what blocks you.

## References

- `references/workflow.md`: each workflow step in detail, the stop criteria, variants and scenes.
- `references/modelling-api.md`: the part program API and the build report.
- `references/palette-and-shading.md`: palette roles, slots and variants, and shading settings and defects.
- `references/comfyui-setup.md`: ComfyUI requirements, models and settings.
- `references/knowledge/`: technique and object notes with runnable samples.
