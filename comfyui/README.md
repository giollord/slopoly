# ComfyUI workflows

Development sources of the ComfyUI workflows that the `slopoly` CLI ships in `src/slopoly/comfy/workflows/` and runs
on the user's ComfyUI over its HTTP API. The required models are listed in `src/slopoly/comfy/models.yaml` (which
`slopoly doctor --fetch` downloads from) and below.

## Required models

All are free to download (no Hugging Face sign-in) and allow commercial use of their outputs. Krea 2 Turbo (the
default image model) does so only under limits: under the Krea 2 Community License, its images may be used
commercially only while the user's company has under $1M yearly revenue, with content filtering. The fallback
Z-Image Turbo (`slopoly config set images.model z-image-turbo`) has no such limits. The licence checks are in
`openspec/changes/archive/2026-11-14-hero-image-and-splat-views/notes.md` and
`openspec/changes/reference-mesh-and-review/notes.md`. Put each file in its subfolder of `<models-dir>`:

| File | Subfolder | Size | Used by | Licence |
|---|---|---|---|---|
| [flux2-vae.safetensors](https://huggingface.co/Comfy-Org/flux2-dev/resolve/main/split_files/vae/flux2-vae.safetensors) | `vae` | 0.3 GB | idol-mesh (Idol conditioning) | Apache 2.0 |
| [krea2_turbo_int8_convrot.safetensors](https://huggingface.co/Comfy-Org/Krea-2/resolve/main/diffusion_models/krea2_turbo_int8_convrot.safetensors) | `diffusion_models` | 13.5 GB | style-anchor, hero | Krea 2 Community License |
| [krea2_style_reference.safetensors](https://huggingface.co/Comfy-Org/Krea-2/resolve/main/loras/krea2_style_reference.safetensors) | `loras` | 0.5 GB | style-anchor, hero | Krea 2 Community License |
| [qwen3vl_4b_bf16.safetensors](https://huggingface.co/Comfy-Org/Mage-Flow/resolve/main/text_encoders/qwen3vl_4b_bf16.safetensors) | `text_encoders` | 8.9 GB | style-anchor, hero | Apache 2.0 |
| [qwen_image_vae.safetensors](https://huggingface.co/Comfy-Org/Krea-2/resolve/main/vae/qwen_image_vae.safetensors) | `vae` | 0.3 GB | style-anchor, hero | Apache 2.0 |
| [z_image_turbo_int8_convrot.safetensors](https://huggingface.co/Comfy-Org/z_image_turbo/resolve/main/split_files/diffusion_models/z_image_turbo_int8_convrot.safetensors) | `diffusion_models` | 6.2 GB | `*.z-image-turbo` | Apache 2.0 |
| [qwen_3_4b_fp8_mixed.safetensors](https://huggingface.co/Comfy-Org/z_image_turbo/resolve/main/split_files/text_encoders/qwen_3_4b_fp8_mixed.safetensors) | `text_encoders` | 5.6 GB | `*.z-image-turbo` | Apache 2.0 |
| [ae.safetensors](https://huggingface.co/Comfy-Org/z_image_turbo/resolve/main/split_files/vae/ae.safetensors) | `vae` | 0.3 GB | `*.z-image-turbo` | Apache 2.0 |
| [idol_fp16.safetensors](https://huggingface.co/Comfy-Org/Idol/resolve/main/diffusion_models/idol_fp16.safetensors) | `diffusion_models` | 0.7 GB | idol-mesh | Apache 2.0 |
| [idol_decoder_fp16.safetensors](https://huggingface.co/Comfy-Org/Idol/resolve/main/vae/idol_decoder_fp16.safetensors) | `vae` | 0.6 GB | idol-mesh | Apache 2.0 |
| [dino_v3_vit_h_bf16.safetensors](https://huggingface.co/Comfy-Org/Idol/resolve/main/clip_vision/dino_v3_vit_h_bf16.safetensors) | `clip_vision` | 1.7 GB | idol-mesh | DINOv3 License |
| [birefnet.safetensors](https://huggingface.co/Comfy-Org/BiRefNet/resolve/main/background_removal/birefnet.safetensors) | `background_removal` | 0.4 GB | idol-mesh, reference-mesh | MIT |
| [trellis_2_int8_convrot.safetensors](https://huggingface.co/Comfy-Org/TRELLIS.2/resolve/main/diffusion_models/trellis_2_int8_convrot.safetensors) | `diffusion_models` | 5.3 GB | reference-mesh (TRELLIS.2) | MIT |
| [trellis_2_shape_vae_bf16.safetensors](https://huggingface.co/Comfy-Org/Pixal3D/resolve/main/vae/trellis_2_shape_vae_bf16.safetensors) | `vae` | 1.1 GB | reference-mesh | MIT |
| [trellis_2_texture_vae_bf16.safetensors](https://huggingface.co/Comfy-Org/Pixal3D/resolve/main/vae/trellis_2_texture_vae_bf16.safetensors) | `vae` | 0.9 GB | reference-mesh | MIT |
| [dino_v3_L_naf_fp32.safetensors](https://huggingface.co/Comfy-Org/Pixal3D/resolve/main/clip_vision/dino_v3_L_naf_fp32.safetensors) | `clip_vision` | 1.2 GB | reference-mesh | DINOv3 License (Built with DINOv3); NAF upsampler Apache 2.0 |
| [pixal3d_int8_convrot.safetensors](https://huggingface.co/Comfy-Org/Pixal3D/resolve/main/diffusion_models/pixal3d_int8_convrot.safetensors) | `diffusion_models` | 5.6 GB | reference-mesh (Pixal3D) | MIT |
| [moge_2_vitl_normal_fp16.safetensors](https://huggingface.co/Comfy-Org/MoGe/resolve/main/geometry_estimation/moge_2_vitl_normal_fp16.safetensors) | `geometry_estimation` | 0.7 GB | reference-mesh (Pixal3D's camera) | MIT |
| [sam3.1_multiplex_fp16.safetensors](https://huggingface.co/Comfy-Org/sam3.1/resolve/main/checkpoints/sam3.1_multiplex_fp16.safetensors) | `checkpoints` | 1.7 GB | segment-parts | SAM License |

Download each with `curl -L -o <subfolder>/<file> <url>` from `<models-dir>`. A job whose model is missing fails with a
`missing_model` error that names the file; `slopoly doctor --fetch` downloads missing models into
`comfyui.models_dir`.

## Workflows

| Workflow | What it does | Named inputs | Output |
|---|---|---|---|
| `style-anchor` | Krea 2 Turbo (int8, 8 steps), 1344x768 scene, with up to 3 style references | `prompt`, `seed`, `use_references`, `reference_1..3`, `use_reference_1..3` | `image` |
| `hero` | Same model, 1024x1024 single object (a three-quarter front view); the pack's picked anchors are the references | same | `image` |
| `idol-mesh` | Rough 3D mesh of a hero with vertex colours (the default generator): an Idol (TripoSplat) Gaussian splat turned into a mesh with `SplatToMesh` and decimated to `faces` | `image`, `seed`, `faces` | `mesh` (GLB), `hero_mask` |
| `reference-mesh` | Rough 3D mesh of a hero with vertex colours: TRELLIS.2 or Pixal3D (`in:trellis2` false), cut down from the gallery template `3d_pixal3d_trellis2_image_to_model` to its shape and vertex-colour path (no UV unwrap or texture bakes), decimated to `faces` | `image`, `seed`, `trellis2`, `resolution`, `faces` | `mesh` (GLB), `hero_mask` |
| `style-anchor.z-image-turbo`, `hero.z-image-turbo` | The fallback image model (`images.model z-image-turbo`): Z-Image Turbo (int8, 8 steps) at the same sizes, text only | `prompt`, `seed` | `image` |
| `segment-parts` | SAM 3.1 text-prompted mask (threshold 0.5) of one part in one view image | `image`, `prompt` | `mask` |

The Krea image wiring follows the gallery templates `image_krea2_turbo_t2i_int8` and
`image_krea2_turbo_int8_image_style_reference`. `in:use_references` switches (`ComfySwitchNode`) between plain text
to image (`CLIPTextEncode`, the base model) and the style-reference path: Krea's style-reference LoRA with
`ModelSamplingFlux`, and `TextEncodeQwenImageEditPlus` with the references as images 1-3 and
`FluxKontextMultiReferenceLatentMethod`. Each reference slot sits behind a `ComfySwitchNode` driven by
`use_reference_<n>` whose `on_false` is unconnected, so an empty slot passes no image (it still needs an existing
file, a placeholder). `gen revise` regenerates from the same prompt with a fresh seed, its source image as the first
reference when a change is given. The Z-Image wiring follows `image_z_image_turbo_int8`. Krea 2 Turbo replaced
Mage-Flow-Edit Turbo after a comparison with MOSS-Image, Chroma1-HD, Z-Image (Turbo and base) and HiDream-O1 (see
`openspec/changes/reference-mesh-and-review/notes.md`). The `idol-mesh` wiring follows the gallery template `3d_idol_image_to_gaussian_splat` (BiRefNet background removal,
DINOv3 conditioning, Idol sampling and decoding), with `SplatToMesh` and `DecimateMesh` in place of its video. It
won the reference-mesh benchmark against TRELLIS.2 and Pixal3D (see
`openspec/changes/reference-mesh-and-review/notes.md`). The
segmentation wiring follows `utility_image_segment_sam3`.

## Editing workflows (development)

Workflows are built with the `comfy` CLI against a running ComfyUI, never in the ComfyUI GUI. Point the CLI at it:

```sh
export COMFY_LOCAL_URL=http://127.0.0.1:8188
```

- `source/<name>.json` holds the editable (UI-format) graphs. Change them with structured edits, for example
  `comfy workflow set-widget source/segment-parts.json <node>.threshold 0.5`.
- Recipes build graphs into an empty source:
  - `recipes/krea2-references.recipe.json` builds both Krea image graphs into an empty source, for example
    `comfy workflow apply source/hero.json --ops recipes/krea2-references.recipe.json --param width=1024 --param height=1024 --param prefix=slopoly/hero`
    (the anchor: `width=1344 height=768 prefix=slopoly/anchor`); `recipes/z-image-turbo.recipe.json` builds
    `hero.z-image-turbo` and `style-anchor.z-image-turbo` with the same params;
  - `recipes/reference-mesh.recipe.json` builds `reference-mesh` into an empty source:
    `comfy workflow apply source/reference-mesh.json --ops recipes/reference-mesh.recipe.json`;
  - `recipes/idol-mesh.recipe.json` builds `idol-mesh` into an empty source:
    `comfy workflow apply source/idol-mesh.json --ops recipes/idol-mesh.recipe.json`.
- `./export.sh` compiles every source into the API-format `src/slopoly/comfy/workflows/<name>.json` that the CLI runs.
  Run it after every change, and keep the model list in `src/slopoly/comfy/models.yaml` in step.
- `reference/` holds the gallery templates the graphs were derived from.

The conventions:

- Nodes titled `in:<name>` receive job values in their main widget.
- Save nodes titled `out:<name>` are the outputs.
- Keep the names in the table above, because the CLI relies on them.
