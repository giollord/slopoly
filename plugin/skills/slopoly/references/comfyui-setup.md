# ComfyUI setup

Slopoly runs its image workflows on the user's own ComfyUI over its HTTP API. It doesn't install ComfyUI or its
nodes. `slopoly doctor` reports what is missing; this note explains how to fix it. Leave installing software and
downloading models to the user, or ask them before you do it.

## Settings

Machine settings are kept outside the workspace (`slopoly config show` lists them):

- `slopoly config set comfyui.url http://127.0.0.1:8188` sets the URL. ComfyUI may run on another machine, because
  images are uploaded and downloaded through the API.
- `slopoly config set comfyui.models_dir <ComfyUI models folder>` lets `slopoly doctor --fetch` download missing
  models into it. Ask the user for this folder.
- `slopoly config set blender.path <blender executable>` is only needed when Blender is not found automatically
  (Blender 5.0 or newer is required).

## Nodes

The workflows need a recent ComfyUI with these core nodes:

- **Qwen-Image-Edit:** `TextEncodeQwenImageEditPlus`, `FluxKontextImageScale` and `ComfySwitchNode`.
- **Splat views:** `TripoSplatPreprocessImage`, `TripoSplatConditioning`, `VAEDecodeTripoSplat`, `RenderSplat` and
  `CreateCameraInfo`.
- **Background removal:** `LoadBackgroundRemovalModel` and `RemoveBackground`.
- **Segmentation:** `SAM3_Detect`.

They were tested with ComfyUI 0.45.3. When doctor lists missing node classes, the usual fix is to update ComfyUI
(`git pull` and reinstall its requirements, `comfy update`, or the desktop app's updater).

## Models

All models are free to download without a sign-in, and their licences allow commercial use of the outputs:

| File | Subfolder | Size | Used by | Licence |
|---|---|---|---|---|
| flux2-vae.safetensors | vae | 0.3 GB | views | Apache 2.0 |
| qwen_image_edit_2511_fp8mixed.safetensors | diffusion_models | 20.5 GB | anchors, heroes | Apache 2.0 |
| qwen_2.5_vl_7b_fp8_scaled.safetensors | text_encoders | 9.4 GB | anchors, heroes | Apache 2.0 |
| qwen_image_vae.safetensors | vae | 0.3 GB | anchors, heroes | Apache 2.0 |
| Qwen-Image-Edit-2511-Lightning-4steps-V1.0-bf16.safetensors | loras | 0.8 GB | anchors, heroes | Apache 2.0 |
| idol_fp16.safetensors | diffusion_models | 0.7 GB | views | Apache 2.0 |
| idol_decoder_fp16.safetensors | vae | 0.6 GB | views | Apache 2.0 |
| dino_v3_vit_h_bf16.safetensors | clip_vision | 1.7 GB | views | DINOv3 License |
| birefnet.safetensors | background_removal | 0.4 GB | views | MIT |
| sam3.1_multiplex_fp16.safetensors | checkpoints | 1.7 GB | segmentation | SAM License |

To get them:

- Run `slopoly doctor --fetch`. It downloads the missing ones into `comfyui.models_dir`, resuming partial downloads.
- Or print the URLs with `slopoly doctor` (the `missing` list) and download them by hand.

The workflows are designed for a 12 GB GPU. Only one generation runs at a time, because ComfyUI's own queue runs them
in order.
