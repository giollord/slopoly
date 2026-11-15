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
