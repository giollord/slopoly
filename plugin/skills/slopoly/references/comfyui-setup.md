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

- **Anchors and heroes (Mage-Flow-Edit):** `TextEncodeMageFlowEdit`, `EmptyImage` and `ComfySwitchNode`.
- **Reference mesh (Idol):** `TripoSplatPreprocessImage`, `TripoSplatConditioning`, `VAEDecodeTripoSplat`,
  `SplatToMesh`, `DecimateMesh` and `SaveGLB`.
- **Reference mesh (TRELLIS.2 and Pixal3D, optional generators):** the `Trellis2*`, `Pixal3DConditioning`, `MoGe*`
  and `PaintMesh` nodes.
- **Background removal:** `LoadBackgroundRemovalModel` and `RemoveBackground`.
- **Segmentation:** `SAM3_Detect`.

They were tested with ComfyUI 0.38.0. `slopoly doctor` lists every missing node class with the workflows that use it.
The usual fix is to update ComfyUI (`git pull` and reinstall its requirements, `comfy update`, or the desktop app's
updater).

## Models

All models are free to download without a sign-in, and their licences allow commercial use of the outputs:

| File | Subfolder | Size | Used by | Licence |
|---|---|---|---|---|
| mage_flow_edit_turbo_int8_convrot.safetensors | diffusion_models | 4.2 GB | anchors, heroes | MIT |
| qwen3vl_4b_bf16.safetensors | text_encoders | 8.9 GB | anchors, heroes | Apache 2.0 |
| mage_flow_vae_bf16.safetensors | vae | 0.3 GB | anchors, heroes | MIT |
| flux2-vae.safetensors | vae | 0.3 GB | views (Idol) | Apache 2.0 |
| idol_fp16.safetensors | diffusion_models | 0.7 GB | views (Idol) | Apache 2.0 |
| idol_decoder_fp16.safetensors | vae | 0.6 GB | views (Idol) | Apache 2.0 |
| dino_v3_vit_h_bf16.safetensors | clip_vision | 1.7 GB | views (Idol) | DINOv3 License |
| birefnet.safetensors | background_removal | 0.4 GB | views | MIT |
| trellis_2_int8_convrot.safetensors | diffusion_models | 5.3 GB | views (`--generator trellis2`) | MIT |
| trellis_2_shape_vae_bf16.safetensors | vae | 1.1 GB | views (`--generator trellis2/pixal3d`) | MIT |
| trellis_2_texture_vae_bf16.safetensors | vae | 0.9 GB | views (`--generator trellis2/pixal3d`) | MIT |
| dino_v3_L_naf_fp32.safetensors | clip_vision | 1.2 GB | views (`--generator trellis2/pixal3d`) | DINOv3 License |
| pixal3d_int8_convrot.safetensors | diffusion_models | 5.6 GB | views (`--generator pixal3d`) | MIT |
| moge_2_vitl_normal_fp16.safetensors | geometry_estimation | 0.7 GB | views (`--generator pixal3d`) | MIT |
| sam3.1_multiplex_fp16.safetensors | checkpoints | 1.7 GB | segmentation | SAM License |

To get them:

- Run `slopoly doctor --fetch`. It downloads the missing ones into `comfyui.models_dir`, resuming partial downloads.
- Or print the URLs with `slopoly doctor` (the `missing` list) and download them by hand.

The workflows are designed for a 12 GB GPU. Only one generation runs at a time, because ComfyUI's own queue runs them
in order.

## Updating slopoly

Close slopoly's windows (pick, view, review) and wait for running jobs (`slopoly jobs`) before reinstalling. On
Windows a running job holds `slopoly.exe` open, so `uv tool install --force` fails halfway and leaves slopoly
uninstalled until the job ends and the install is run again.
