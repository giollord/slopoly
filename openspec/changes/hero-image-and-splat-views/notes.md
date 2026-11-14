# Notes: hero-image-and-splat-views

## Licences (task 1.1, checked 2026-11-14)

The question for each model: may its outputs be used commercially? This is not legal advice. The sources are the
model cards and LICENSE files.

| Model | Used by | Licence | Commercial use |
|---|---|---|---|
| FLUX.2 klein 4B (fp8), FLUX.2 VAE | style-anchor, hero | Apache 2.0 | OK |
| Qwen 3 4B text encoder | style-anchor, hero (klein) | Apache 2.0 | OK |
| Idol (`idol_fp16`, `idol_decoder_fp16`) | views | Apache 2.0 (a fine-tune of TripoSplat, which is MIT) | OK |
| BiRefNet | views (background removal) | MIT | OK |
| DINOv3 ViT-H (`dino_v3_vit_h_bf16`) | views (Idol image encoder) | DINOv3 License | OK with conditions: see below |
| SAM 3.1 | segment-parts | SAM License | OK with conditions: see below |
| Qwen-Image-Edit-2511 | bake-off candidate | Apache 2.0 | OK |
| Qwen2.5-VL 7B (text encoder) | bake-off candidate | Apache 2.0 (the 7B model; some other sizes have other licences) | OK |
| Qwen-Image-Edit-2511-Lightning LoRA | bake-off candidate | Apache 2.0 | OK |

**DINOv3 and SAM licences (Meta).** Both give a worldwide, royalty-free licence to use, modify and distribute, with
no non-commercial clause. Their conditions:

- no military, weapons or espionage use, and trade controls apply;
- redistributing the model files requires including the licence;
- research publications must credit the model;
- the user indemnifies Meta;
- the licence ends if you sue Meta over the materials.

The generated images, splats and assets are not "Materials", so shipping them in a product is not restricted.
Shipping the model files themselves would require including the licence.

## Qwen load test (task 1.3)

The gallery template `image_qwen_image_edit_2511` was run unchanged except for the inputs: the fp8mixed model, the fp8
Qwen2.5-VL 7B text encoder and the Lightning 4-step LoRA (4 steps, CFG 1), with one input image. No custom nodes were
needed and nothing ran out of memory.

| Run | Time | Peak VRAM | Container RAM after |
|---|---|---|---|
| Cold (models load from disk) | 93 s | not sampled | 26.4 GiB |
| Warm | 32 s | 11.7 GB of 12 GB | 26.7 GiB of the 31.3 GiB Docker limit |

ComfyUI keeps the part of the 20.5 GB model that doesn't fit in VRAM in RAM. The container's RAM is close to the Docker
Desktop limit, so the WSL memory limit may need raising if Qwen and other models are loaded together.

## Views calibration (task 3.3)

The stand-in hero was the cart view from the old turnaround sheet, scaled to 768 px. The `views` workflow ran it in
88 s cold and 54 s warm, giving 72 frames per turntable. The views agree across angles and the bed is visibly hollow.
The object filled too little of the frame at zoom 1, so the recipe uses zoom 2.5.

- **Front.** Symmetry peaked at about 0.6 (the handles keep it below 0.8), so the peak threshold is 0.5 plus 1.3 times
  the median. The front was detected at frame 35, the end without handles, which faces the hero.
- **Side.** Frame 35 - 18 shows the cart from +X with its front on the image's left, as `slopoly_model` expects, so
  `QUARTER_SIGN = -1`.
- **Top.** Above frame 35 shows the front at the bottom.
- **Known limits.**
  - With a pure side-view stand-in, the front and back peaks are nearly tied. A real three-quarter hero settles it.
  - The top view is tilted by up to 2.5 degrees because the yaw comes in 5-degree steps (72 frames).

**The first real hero (the user's picked cart) broke single-frame symmetry.** The cart is nearly symmetric from the
side too, so the median symmetry was 0.71 and no peak passed 1.3 times it. The front was "assumed" at 110 degrees,
about 20 degrees off end-on, which also tilted the top view. Two changes fixed it:

- **Mirror-plane score.** The score averages mirror pairs t ± d. The plane at 92.5 degrees scored 0.78 against a median
  of 0.61, while the side directions reached only 0.65. The old stand-in still gives frame 36.
- **Colour in the hero match.** For a mirror-symmetric object, silhouettes can't tell front from back, so the match
  also compares colours.

A new views run on the picked cart reported `detected` at 270 degrees. The front and back are end-on, the top is
straight, and the side shows the hero's near end on the left.

## Bake-off (task 7.1)

Both models got the same prompts and seeds (11 and 22). The prompts were:

- the village scene, as a style anchor with no references (the pack has no uploaded style references);
- the cart hero, with the picked village anchor as reference;
- a gnome-house hero, with the picked village anchor as reference.

The user rated each pair blind (A = klein, B = Qwen) on style, correctness and placement together.

| Prompt | Seed 11 | Seed 22 |
|---|---|---|
| Village scene | Qwen | Qwen |
| Cart hero | tie | Qwen |
| House hero | tie | Qwen |

| Model | First image (includes loading) | Warm, per image | Peak VRAM |
|---|---|---|---|
| FLUX.2 klein 4B fp8 | 21 s | 4-7 s | 11.7 GB |
| Qwen-Image-Edit-2511 fp8mixed, Lightning 4 steps | 62 s | 13-31 s (79 s when the references first change) | 11.8 GB |

A new reference set means the Qwen text encoder (which also reads the images) runs again, hence the slower first
hero. Qwen also followed the brief more closely: its carts have two wheels and two long handles, as the cart's
description asks.

**Decision:** Qwen-Image-Edit-2511 for both `style-anchor` and `hero`. It wins 4 of 6 pairs and loses none, at about
three times klein's time. The klein workflows, its recipe and template and the Qwen 3 4B text encoder are no longer
used; the FLUX.2 VAE stays because Idol's conditioning uses it.

## Cart run (task 7.2)

The user picked a hero (four wheels, handles at both ends) and made its views; the front was then detected at 270
degrees. Asked to continue, the agent segmented the views, added one palette role ("wood inside"), read the knowledge
notes, saved a manifest and iterated through 5 builds. It modelled a hollow bed with chipped plank edges, two axles,
four wheels and four handles, at 488 of 2000 triangles. The whole turn took about 2 minutes: segmentation 19 s, each
build a few seconds.

| Build | Validated | Front | Side | Top | Back | Mean object IoU |
|---|---|---|---|---|---|---|
| 1 | yes | 0.63 | 0.66 | 0.68 | 0.63 | 0.65 |
| 2 | yes | 0.70 | 0.90 | 0.79 | 0.70 | 0.77 |
| 3 (final) | yes | 0.72 | 0.90 | 0.80 | 0.72 | 0.785 |
| 4 | no (a 5 mm gap) | 0.72 | 0.90 | 0.80 | 0.72 | 0.785 |

**Outcome:** validated, but just short of the stop rule (mean object IoU 0.785 against 0.8; every view is above
0.7). The agent stopped as instructed after attempts that didn't improve, and reported the blocker: its straight
handle sweeps and solid wheel discs don't capture the hero's curved handles and spoked wheels. The front and back
scores are always equal, because an orthographic back view is the mirror of the front and the model is
mirror-symmetric.

**Two pipeline bugs found and fixed during the run:**

- **Part scores were all unmatched.** A mask named `wheel` only matched `wheel`, `wheel_L`/`wheel_R` or a mesh called
  `wheel`, but the agent named its parts `wheel_front_L` and so on. A mask now also matches every part whose name
  starts with its name and an underscore.
- **Segmentation kept one instance per part.** SAM 3 returns only the best object for a text prompt unless the prompt
  says `name:N`, so the "wheel" mask was one wheel. The worker now asks for up to 8 instances per part.

Re-scoring the same program with the fixed segmentation raised the mean part IoU from 0.27 to 0.40, and the wheel
width errors fell from about +0.9 to +0.05 (side wheel IoU 0.91). The bed comes back as the whole object (expected),
and the axle masks are unreliable: the side one is a 712 x 297 px box. The object scores are unchanged.

**Next steps for the cart** (the user's call): bend the handles and cut spoke gaps into the wheels, as the agent
suggests, or accept 0.785 as "looks right".
