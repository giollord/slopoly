# ComfyUI workflows

The comfy worker (`containers/comfyui`) runs these workflows on the ComfyUI inside its container. The models are not
in the image: the AppHost bind-mounts your models folder (`comfyui-models-dir`, see the root README) at
`/opt/ComfyUI/models`.

## Required models

All are free to download (no Hugging Face sign-in) and allow commercial use of their outputs; the licence check is in
`openspec/changes/hero-image-and-splat-views/notes.md`. Put each file in its subfolder of `<models-dir>`:

| File | Subfolder | Size | Used by | Licence |
|---|---|---|---|---|
| [flux2-vae.safetensors](https://huggingface.co/Comfy-Org/flux2-dev/resolve/main/split_files/vae/flux2-vae.safetensors) | `vae` | 0.3 GB | views (Idol conditioning) | Apache 2.0 |
| [qwen_image_edit_2511_fp8mixed.safetensors](https://huggingface.co/Comfy-Org/Qwen-Image-Edit_ComfyUI/resolve/main/split_files/diffusion_models/qwen_image_edit_2511_fp8mixed.safetensors) | `diffusion_models` | 20.5 GB | style-anchor, hero | Apache 2.0 |
| [qwen_2.5_vl_7b_fp8_scaled.safetensors](https://huggingface.co/Comfy-Org/HunyuanVideo_1.5_repackaged/resolve/main/split_files/text_encoders/qwen_2.5_vl_7b_fp8_scaled.safetensors) | `text_encoders` | 9.4 GB | style-anchor, hero | Apache 2.0 |
| [qwen_image_vae.safetensors](https://huggingface.co/Comfy-Org/Qwen-Image_ComfyUI/resolve/main/split_files/vae/qwen_image_vae.safetensors) | `vae` | 0.3 GB | style-anchor, hero | Apache 2.0 |
| [Qwen-Image-Edit-2511-Lightning-4steps-V1.0-bf16.safetensors](https://huggingface.co/lightx2v/Qwen-Image-Edit-2511-Lightning/resolve/main/Qwen-Image-Edit-2511-Lightning-4steps-V1.0-bf16.safetensors) | `loras` | 0.8 GB | style-anchor, hero | Apache 2.0 |
| [idol_fp16.safetensors](https://huggingface.co/Comfy-Org/Idol/resolve/main/diffusion_models/idol_fp16.safetensors) | `diffusion_models` | 0.7 GB | views | Apache 2.0 |
| [idol_decoder_fp16.safetensors](https://huggingface.co/Comfy-Org/Idol/resolve/main/vae/idol_decoder_fp16.safetensors) | `vae` | 0.6 GB | views | Apache 2.0 |
| [dino_v3_vit_h_bf16.safetensors](https://huggingface.co/Comfy-Org/Idol/resolve/main/clip_vision/dino_v3_vit_h_bf16.safetensors) | `clip_vision` | 1.7 GB | views | DINOv3 License |
| [birefnet.safetensors](https://huggingface.co/Comfy-Org/BiRefNet/resolve/main/background_removal/birefnet.safetensors) | `background_removal` | 0.4 GB | views | MIT |
| [sam3.1_multiplex_fp16.safetensors](https://huggingface.co/Comfy-Org/sam3.1/resolve/main/checkpoints/sam3.1_multiplex_fp16.safetensors) | `checkpoints` | 1.7 GB | segment-parts | SAM License |

Download each with `curl -L -o <subfolder>/<file> <url>` from `<models-dir>`. A job whose model is missing fails with a
`missing_model` error that names the file.

## Workflows

| Workflow | What it does | Named inputs | Output |
|---|---|---|---|
| `style-anchor` | Qwen-Image-Edit-2511 (fp8mixed, Lightning 4 steps), 1344x768 scene with up to 3 style references | `prompt`, `seed`, `reference_1..3`, `use_reference_1..3` | `image` |
| `hero` | Same model, 1024x1024 single object (a three-quarter front view); the pack's picked anchors are the references | same | `image` |
| `views` | Idol (TripoSplat) Gaussian splat of a hero, rendered as two orthographic 72-frame turntables (eye level and from above, 768 px) with silhouettes | `image`, `seed` | `ring`, `ring_mask`, `above`, `above_mask`, `hero_mask` |
| `segment-parts` | SAM 3.1 text-prompted mask (threshold 0.5) of one part in one view image | `image`, `prompt` | `mask` |

The reference wiring follows the gallery template `image_qwen_image_edit_2511`: each reference is scaled with
`FluxKontextImageScale` and given to `TextEncodeQwenImageEditPlus` (as image 1-3) for both the prompt and the empty
negative; the image is sampled from an empty latent at the workflow's size. Each slot sits behind a `ComfySwitchNode`
driven by `use_reference_<n>` whose `on_false` is unconnected, so an empty slot passes no image (it still needs an
existing file, a placeholder). Qwen won the bake-off against FLUX.2 klein 4B (see
`openspec/changes/hero-image-and-splat-views/notes.md`). The `views` wiring follows the gallery template `3d_idol_image_to_gaussian_splat` (BiRefNet background removal,
DINOv3 conditioning, Idol sampling and decoding), with native `RenderSplat` turntables in place of its video. The
segmentation wiring follows `utility_image_segment_sam3`.

## Editing workflows (development)

Workflows are built with the `comfy` CLI against the container's ComfyUI, never in the ComfyUI GUI. The container
publishes ComfyUI on `http://127.0.0.1:8288`, so start the stack and point the CLI there:

```sh
export COMFY_LOCAL_URL=http://127.0.0.1:8288
```

- `source/<name>.json` holds the editable (UI-format) graphs. Change them with structured edits, for example
  `comfy workflow set-widget source/segment-parts.json <node>.threshold 0.5`.
- Recipes build graphs into an empty source:
  - `recipes/qwen-image-edit-references.recipe.json` builds both image graphs, for example
    `comfy workflow apply source/hero.json --ops recipes/qwen-image-edit-references.recipe.json --param width=1024 --param height=1024 --param prefix=slopoly/hero`;
  - `recipes/idol-views.recipe.json` builds `views`:
    `comfy workflow apply source/views.json --ops recipes/idol-views.recipe.json`.
- `./export.sh` compiles every source into the API-format `workflows/<name>.json` that the worker runs. Run it after
  every change. The workflows folder is mounted into the container, so no rebuild is needed.
- `reference/` holds the gallery templates the graphs were derived from.

The conventions:

- Nodes titled `in:<name>` receive job values in their main widget.
- Save nodes titled `out:<name>` are the outputs.
- Keep the names in the table above, because the worker relies on them.
