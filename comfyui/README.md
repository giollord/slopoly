# ComfyUI workflows

The comfy worker (`containers/comfyui`) runs these workflows on the ComfyUI inside its container. The models are not
in the image: the AppHost bind-mounts your models folder (`comfyui-models-dir`, see the root README) at
`/opt/ComfyUI/models`.

## Required models

All four are free to download (no Hugging Face sign-in). Put them in these subfolders of `<models-dir>`:

| File | Subfolder | Size | Used by | Licence |
|---|---|---|---|---|
| [flux-2-klein-4b-fp8.safetensors](https://huggingface.co/black-forest-labs/FLUX.2-klein-4b-fp8/resolve/main/flux-2-klein-4b-fp8.safetensors) | `diffusion_models` | 4.1 GB | style-anchor, turnaround | Apache 2.0 |
| [qwen_3_4b.safetensors](https://huggingface.co/Comfy-Org/z_image_turbo/resolve/main/split_files/text_encoders/qwen_3_4b.safetensors) | `text_encoders` | 8.0 GB | style-anchor, turnaround | Apache 2.0 |
| [flux2-vae.safetensors](https://huggingface.co/Comfy-Org/flux2-dev/resolve/main/split_files/vae/flux2-vae.safetensors) | `vae` | 0.3 GB | style-anchor, turnaround | Apache 2.0 |
| [sam3.1_multiplex_fp16.safetensors](https://huggingface.co/Comfy-Org/sam3.1/resolve/main/checkpoints/sam3.1_multiplex_fp16.safetensors) | `checkpoints` | 1.7 GB | segment-parts | SAM License |

For example, from `<models-dir>`:

```sh
curl -L -o diffusion_models/flux-2-klein-4b-fp8.safetensors https://huggingface.co/black-forest-labs/FLUX.2-klein-4b-fp8/resolve/main/flux-2-klein-4b-fp8.safetensors
curl -L -o text_encoders/qwen_3_4b.safetensors https://huggingface.co/Comfy-Org/z_image_turbo/resolve/main/split_files/text_encoders/qwen_3_4b.safetensors
curl -L -o vae/flux2-vae.safetensors https://huggingface.co/Comfy-Org/flux2-dev/resolve/main/split_files/vae/flux2-vae.safetensors
curl -L -o checkpoints/sam3.1_multiplex_fp16.safetensors https://huggingface.co/Comfy-Org/sam3.1/resolve/main/checkpoints/sam3.1_multiplex_fp16.safetensors
```

A job whose model is missing fails with a `missing_model` error that names the file.

## Workflows

| Workflow | What it does | Named inputs | Output |
|---|---|---|---|
| `style-anchor` | FLUX.2 [klein] 4B, 1344x768 scene with up to 3 style references | `prompt`, `seed`, `reference_1..3`, `use_reference_1..3` | `image` |
| `turnaround` | Same model, 1536x512 front/side/top sheet; the pack's picked anchor is reference 1 | same | `image` |
| `segment-parts` | SAM 3.1 text-prompted mask (threshold 0.5) of one part in one view crop | `image`, `prompt` | `mask` |

The reference wiring follows the gallery template `image_flux2_klein_image_edit_4b_distilled`: each reference is scaled
to 1 MP, VAE-encoded and chained with `ReferenceLatent` on both the prompt and the zeroed negative. Each slot sits
behind a `ComfySwitchNode` driven by `use_reference_<n>`, so empty slots (which get a black placeholder image) change
nothing. The segmentation wiring follows `utility_image_segment_sam3`.

## Editing workflows (development)

Workflows are built with the `comfy` CLI against the container's ComfyUI, never in the ComfyUI GUI. The container
publishes ComfyUI on `http://127.0.0.1:8288`, so start the stack and point the CLI there:

```sh
export COMFY_LOCAL_URL=http://127.0.0.1:8288
```

- `source/<name>.json` holds the editable (UI-format) graphs. Change them with structured edits, for example
  `comfy workflow set-widget source/segment-parts.json <node>.threshold 0.5`.
- `recipes/flux2-klein-references.recipe.json` builds both FLUX graphs:
  `comfy workflow apply source/turnaround.json --ops recipes/flux2-klein-references.recipe.json --param width=1536 --param height=512 --param prefix=slopoly/turnaround`.
- `./export.sh` compiles every source into the API-format `workflows/<name>.json` that the worker runs. Run it after
  every change. The workflows folder is mounted into the container, so no rebuild is needed.
- `reference/` holds the gallery templates the graphs were derived from.

The conventions:

- Nodes titled `in:<name>` receive job values in their main widget.
- Save nodes titled `out:<name>` are the outputs.
- Keep the names in the table above, because the worker relies on them.
