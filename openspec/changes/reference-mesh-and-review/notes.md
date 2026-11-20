# Notes

## Licence check (task 1.1, 2026-11-16)

Every model the `reference-mesh` workflow may use, with its source and licence. All of them run locally and allow
commercial use of their outputs.

| File | Subfolder | Source | Licence | Verdict |
|---|---|---|---|---|
| `trellis_2_int8_convrot.safetensors` | `diffusion_models` | [Comfy-Org/TRELLIS.2](https://huggingface.co/Comfy-Org/TRELLIS.2), from [microsoft/TRELLIS.2-4B](https://huggingface.co/microsoft/TRELLIS.2-4B) | MIT | ok |
| `trellis_2_shape_vae_bf16.safetensors` | `vae` | [Comfy-Org/Pixal3D](https://huggingface.co/Comfy-Org/Pixal3D) (also in Comfy-Org/TRELLIS.2) | MIT | ok |
| `trellis_2_texture_vae_bf16.safetensors` | `vae` | same | MIT | ok |
| `pixal3d_int8_convrot.safetensors` | `diffusion_models` | [Comfy-Org/Pixal3D](https://huggingface.co/Comfy-Org/Pixal3D), from [TencentARC/Pixal3D](https://huggingface.co/TencentARC/Pixal3D) | MIT; third-party parts under their own terms (NOTICE): TRELLIS.2 (MIT), Direct3D-S2 | ok |
| `dino_v3_L_naf_fp32.safetensors` | `clip_vision` | [Comfy-Org/Pixal3D](https://huggingface.co/Comfy-Org/Pixal3D) | DINOv3 License (Meta) for the DINOv3 ViT-L weights; NAF upsampler [valeoai/NAF](https://github.com/valeoai/NAF) Apache 2.0 | ok: the same DINOv3 License as the `dino_v3_vit_h` encoder already shipped for Idol (commercial use allowed, "Built with DINOv3" attribution) |
| `moge_2_vitl_normal_fp16.safetensors` | `geometry_estimation` | [Comfy-Org/MoGe](https://huggingface.co/Comfy-Org/MoGe), from [Ruicheng/moge-2-vitl-normal](https://huggingface.co/Ruicheng/moge-2-vitl-normal) | MIT | ok (Pixal3D only: camera field of view) |
| `birefnet.safetensors` | `background_removal` | already shipped | MIT | ok |

Not considered: Hunyuan3D 2.x (Tencent Hunyuan community licence excludes the EU, UK and South Korea).

The DINOv3 License asks for "Built with DINOv3" to be shown; the existing README licence table already covers the
Idol encoder under it, and the new encoder is added to the same table.

## Reference-mesh benchmark (tasks 1.4 and 1.5, 2026-11-16)

`comfyui/benchmark_mesh.py`, seed 7, each run from cold (models unloaded), 80,000-face decimation for every
candidate, one 16 GB GPU. Hero IoU is the mesh's silhouette from its matched hero camera against the hero's
background mask (which includes smoke, so the smoke case scores low for every candidate).

| Hero | Candidate | Seconds | Peak GPU MiB | Hero IoU | Front | Look (contact sheet) |
|---|---|---|---|---|---|---|
| cart | TRELLIS.2 | 80.0 | 11,264 | 0.91 | detected | good, slightly warped bed |
| cart | Pixal3D | 99.9 | 11,675 | 0.85 | detected | warped, bent handles |
| cart | Idol + SplatToMesh | 31.7 | 10,026 | 0.94 | detected | cleanest, straight planks |
| locomotive (no smoke) | TRELLIS.2 | 72.5 | 11,596 | 0.75 | detected | readable, torn sheets and gaps |
| locomotive (no smoke) | Pixal3D | 109.3 | 11,750 | 0.66 | assumed | broken into shards |
| locomotive (no smoke) | Idol + SplatToMesh | 30.7 | 9,426 | 0.80 | detected | coherent: boiler, ribs, cab, wheels, tusks |
| locomotive (smoke) | TRELLIS.2 | 196.4 | 11,909 | 0.65 | assumed | shards |
| locomotive (smoke) | Pixal3D | 120.0 | 11,743 | 0.60 | assumed | shards, the plume modelled |
| locomotive (smoke) | Idol + SplatToMesh | 32.7 | 9,771 | 0.67 | assumed | coherent, the plume left out |

**Decision.** Idol + SplatToMesh (`idol-mesh` workflow, generator `idol`) is the default: best on every hero by
eye and by hero IoU, two to six times faster, and the least GPU memory. It keeps the stylised, chunky shapes of the
heroes, where TRELLIS.2 and Pixal3D tear thin sheets and busy silhouettes into fragments. TRELLIS.2 and Pixal3D stay
as `--generator trellis2|pixal3d` for heroes where the splat is poor. This reverses the plan to remove Idol: the old
`views` turntable workflow is removed (the views are rendered on the host from the mesh), and Idol's models move to
`idol-mesh`. Resolution: TRELLIS.2 at 1024 (its upsample stage); SplatToMesh at 384 (finer grids add noise, not
detail, at the splat's density).

## Image model replaced (task 11.1, 2026-11-17)

Qwen-Image-Edit-2511 took too long per image. Criteria for the replacement: an open-weights model from 2026 or later,
in common use, not FLUX, that runs locally, takes style references, and whose licence allows commercial use with no
revenue or seat limits. Candidates from the ComfyUI template gallery (template uses as reported by the gallery):

| Model | Released | Licence | Gallery uses | Verdict |
|---|---|---|---|---|
| [Mage-Flow-Edit Turbo](https://huggingface.co/Comfy-Org/Mage-Flow) (Microsoft, 4B, 4 steps, 1-3 references) | 2026-07 | MIT (text encoder Qwen3-VL 4B: Apache 2.0) | 127 (67k downloads of the Comfy-Org repack) | **chosen** |
| Krea 2 Turbo (style reference) | 2026-06 | Krea 2 community licence: free commercial use only under revenue/seat limits, content filter required | 9,144 (text to image) | rejected: licence |
| Qwen Image 2.1 (edit) | 2026-09 | Qwen Research License (non-commercial) | 9,019 | rejected: licence |
| FireRed Image Edit 1.1 | 2026-03 | - | 1,424 | rejected: a Qwen-Image-Edit derivative of the same size, no faster |
| FLUX.2 klein | 2026-01 | Apache 2.0 (4B) | 1,150 | rejected: FLUX, lost the earlier bake-off |
| HiDream O1, Boogu 0.1, JoyAI Image Edit | 2026-05 to 07 | - | under 100 | rejected: rarely used |
| MOSS-Image (edit with references) | 2026 | Apache 2.0 | not in this ComfyUI | rejected: 25 steps, needs ComfyUI 0.43 |

Timings on the development machine (one 16 GB GPU, ComfyUI 0.38.0, models unloaded before each model's first run),
the locomotive hero prompt with the orcish anchor as reference, and the anchor's own prompt without references:

| Workflow | Qwen-Image-Edit-2511 (fp8mixed, Lightning 4 steps), cold / warm | Mage-Flow-Edit Turbo (int8, 4 steps), cold / warm |
|---|---|---|
| hero, 1024x1024, 1 reference | 28.5 s / 18.3 s | 9.5 s / 3.7 s |
| style-anchor, 1344x768, no reference | 14.8 s / 10.7 s | 6.7 s / 2.1 s |

Mage-Flow edits its first image: given the anchor as image 1, every hero copied the anchor's whole scene (water
tower, logs, rails, smoke). Without the reference latents (the anchor only seen by the text encoder) the heroes were
single objects but lost the anchor's flat cartoon style. The shipped wiring gives an empty light grey canvas as image 1
and the references as images 2-4, and the job tells the model to draw on the canvas and take only the art style from
the other images. Two of three hero seeds were then a single object in the anchor's style; one still drew the water
tower and logs, and smoke appears in most (it is in the anchor). Heroes are generated in sets and picked, so this is
acceptable; the prompt keeps asking for no smoke. `gen revise` turns the canvas off and edits its source image.

## Image model replaced again (task 11.14, 2026-11-21)

Mage-Flow-Edit Turbo's anchors were scattered piles of props in a flat clip-art style, and its heroes kept the
anchor's rails and smoke. Candidates were compared on ComfyUI 0.45.4 (one 16 GB GPU), with the orcish pack's anchor
prompts (1344x768) and three locomotive hero prompts (1024x1024, the `HERO_IMAGE` wording with the style text), same
seeds for every model, text only unless noted. Times are warm, per image.

| Model | Licence | Time | Result | Verdict |
|---|---|---|---|---|
| Krea 2 Turbo (int8, 8 steps) | Krea 2 Community License | 13 s; 35 s with the style-reference LoRA, first run | Coherent game scenes; heroes whole, chunky and faceted, no smoke and a plain background in all 3 | **chosen** |
| Z-Image Turbo (int8, 8 steps) | Apache 2.0 (2025-11) | 7 s | Clean, simple, flat-coloured objects, less orcish; smoke in all 3 heroes (cfg 1, no negative prompt) | **fallback** |
| Z-Image base (int8, 25 steps, cfg 4) | Apache 2.0 (2026-01) | 31 s | A negative prompt removes most smoke; busier, thinner silhouettes; one hero drifted to flat 2D | rejected: slower, worse shapes for meshing |
| MOSS-Image (int8, 25 steps) | Apache 2.0 | 22-26 s | Detailed scenes; heroes look like detailed renders, smoke despite the prompt | rejected by the user |
| HiDream-O1 dev (fp8, 28 steps) | MIT | 9-13 s | Realistic rendering, smoke and a beige backdrop with debris in all 3 | rejected |
| Chroma1-HD (fp8, 26 steps) | Apache 2.0 (2025-08, FLUX-based) | 55 s | Messy shapes, smoke | rejected |

**Licence.** The Krea 2 Community License (v1, 2026-06-22) allows commercial use of the model and its outputs only
while the user's company, with its affiliates, has under $1M yearly revenue (above that, an enterprise licence), and
asks deployers to apply reasonable content filtering (§2.3, §4.2). Krea claims no ownership of the outputs. This
breaks the spec's old rule of no revenue limits, so the requirement now asks for the limits to be named (README,
`comfyui-setup.md`, `doctor`) and a fallback without them: Z-Image Turbo, chosen with `images.model z-image-turbo`.
It takes no references, so the fallback's anchors and heroes come from the style text alone and record no references.

**Wiring.** One Krea graph per size: plain text to image without references, and Krea's style-reference LoRA
(`TextEncodeQwenImageEditPlus`, `FluxKontextMultiReferenceLatentMethod`, `ModelSamplingFlux`) behind
`in:use_references` when the job has references. Krea's text encoder is Qwen3-VL 4B; the bf16 file slopoly already
listed works in place of the template's fp8 one. There's no edit mode any more, so `gen revise` regenerates with a
fresh seed, with its source as the first style reference when a change is given.

**CLI run** (orcish copy, `anchor_010` picked): Krea hero job with one reference, 2 images in 67 s (cold: the 13.5 GB
model and the LoRA loaded); Krea anchor 13 s; Z-Image Turbo hero job 2 images in 22 s, anchor 10 s. The Krea heroes
took the anchor's darker palette and spikes; the Z-Image heroes are clean but drew smoke.

**Found on the way.** `slopoly wait` crashed once with `PermissionError` reading a job file while the job process
replaced it (Windows); task 11.7 retries only the writer's `os.replace`, not readers.
