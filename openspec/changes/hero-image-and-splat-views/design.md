## Context

See proposal.md for the reasons. Current state:

- **comfy worker** (`containers/comfyui/comfy_worker.py`).
  - Generation operations run a repository workflow once per requested image.
  - `turnaround` splits the result into thirds.
  - `segment-parts` crops view rectangles out of one image. It also runs the detector once for the whole object to
    reject "whole object" masks.
- **ComfyUI** in the container (0.45.3) already has native TripoSplat and splat nodes (`TripoSplatConditioning`,
  `VAEDecodeTripoSplat`, `RenderSplat`, `SplatToMesh`, `File3DToSplat`, `SaveGaussianSplat`, `RemoveBackground`).
  - `CreateCameraInfo` supports `camera_type: orthographic`.
  - `RenderSplat` returns an image and a mask, and with `frames > 1` it renders a turntable as a batch.
- **Your template.** The user's tested template is "3d_idol_image_to_gaussian_splat". It wires BiRefNet background
  removal, the Idol checkpoints (`idol_fp16`, `idol_decoder_fp16`, `dino_v3_vit_h_bf16`, `flux2-vae`) and the render
  and export branches.
- **Scoring.** `slopoly_model.silhouette` scores masks per view. It searches mirror flips and a uniform scale per
  view because the drawn sheets were ambiguous.
- **Hardware.** An RTX 4070 with 12 GB, and one GPU job at a time.

## Goals / Non-Goals

**Goals:**

- Views that agree with each other by construction.
- A known orientation for every view.
- Silhouettes that need no detector.
- One clean image for the user to pick per asset.
- An evidence-based choice of image model.

**Non-Goals:**

- Using the splat or its mesh as asset geometry. Assets stay hand-built low-poly part programs, and the splat is only
  a reference.
- Texture baking from the splat; that belongs to texturing (C).
- Recovering real-world scale. The agent sets dimensions; the views give proportions.

## Decisions

### 1. Hero image replaces the sheet

**The `hero` operation.** Same reference wiring as the style anchor: up to 3 picked anchors. The output is
1024×1024. The prompt template asks for:

- one object, whole and centred;
- a three-quarter front view from the front-left, slightly above;
- a plain light background;
- the style copied from the references, but not their objects.

**Revisions.** `revise_concept` works on heroes unchanged, because it copies the job inputs.

**Alternative rejected:** per-view generation with an edit model. Each view would be a separate sample, so
proportions drift between them.

### 2. One `views` workflow: splat and two turntables

**`views`** (built with the comfy CLI from `recipes/idol-views.recipe.json`, wired after the Idol template):

```
in:image -> RemoveBackground(BiRefNet) -> TripoSplat (Idol, in:seed) -> SPLAT
    +-> RenderSplat(ortho, pitch 0,  72 frames, 768 px) -> out:ring  + out:ring_mask
    +-> RenderSplat(ortho, pitch 89, 72 frames, 768 px) -> out:above + out:above_mask
RemoveBackground mask -> out:hero_mask
```

Both turntables use the same distance and zoom, so every frame shares one pixel scale. Frame k of `above` has the
same yaw as frame k of `ring`.

**How the worker uses it.** It runs `views` once, picks the front frame (decision 3) and keeps four frames: front,
side, back (from `ring`) and top (from `above`), each with its silhouette. No splat file is stored.

**Correcting the front.** The job is rerun with the same seed and a given `frontYaw`. The same seed rebuilds the same
splat, so only the choice of frames changes. A run takes about a minute.

**Why one workflow.** `Load3D` needs a frontend viewport, so a stored splat can't be reloaded headlessly for a cheap
re-render. Rendering full turntables in the same run also gives the symmetry search all 72 directions at full size.

**Alternative rejected:** `SplatToMesh` and rendering the mesh in the geometry worker. That loses colour, which part
segmentation needs, and adds a step.

### 3. Front direction from silhouette symmetry

The front is the object's mirror plane. Under an orthographic camera the turntable axis is the image's centre
column, so if the plane faces direction t, the frame at t + d is the mirror image of the frame at t - d.

- **Mirror plane.** Each candidate t, in half-frame steps, scores the mirror IoU of the frame pairs t ± d averaged over
  d = 0 to 9 frames (0 to 45 degrees). The plane is the best candidate if it scores at least 0.08 above the median
  candidate.
- **Why pairs, not single frames.** Single-frame symmetry was too noisy: on the picked cart it peaked at 70 and 100
  degrees around the true plane at 92.5. A cart is also nearly symmetric from the side, which lifts the median.
- **The hero frame.** The ring frame that best matches the hero image is the direction it was seen from. The match is
  silhouette IoU after normalising the box, times aspect agreement, times colour agreement inside both silhouettes.
  Colour is needed because with a mirror plane the silhouette d degrees off the front equals the one d degrees off the
  back.
- **Front or back.** The plane shows twice, 180 degrees apart; the one nearer the hero frame is the front.
- **Asymmetric objects.** With no clear plane, the hero frame itself is the front. The job then reports
  `front: "assumed"`, so the UI and the agent can ask the user to check it.

**Calibration (task 3.3).** On the cart, the side view is a quarter turn back from the front frame, which puts the
camera on +X with the object's front on the image's left. The constant `QUARTER_SIGN = -1` records this.

**View axes** follow the `slopoly_model` conventions:

| View | Frame |
|---|---|
| front | ring frame `f` (looks from +Z) |
| side | ring frame `f - N/4` (looks from +X) |
| back | ring frame `f + N/2` |
| top | above frame `f` (front at the bottom) |

### 4. Data model

- `ConceptKind` is `Anchor`, `Hero` or `View`.
- `ConceptImage` gains:
  - `View` (front, side, top or back, for views);
  - `SourceConceptId` (a view's hero);
  - `MaskFileId` (a view's silhouette);
  - `FrontYaw` and the views job's `ViewsSeed` (on heroes).
- `Views` (rectangles inside one image) is dropped.

**Migration.** It deletes `Turnaround` concepts and their `PartMasks` before the column changes; the kinds are stored
as strings. The local database only holds test data from the foundation runs.

**Deletion and selection.**

- Deleting a hero deletes its views and their masks.
- Rejecting a hero hides its views.
- Views have no selection of their own. They are usable while their hero is picked.

### 5. Segmentation per view image, whole-object mask from the render

`segment-parts` gets a hero id. The API expands it to the hero's view images, each with its silhouette mask. For each
view the worker:

- runs SAM 3.1 per part on the whole view image, with no cropping;
- uses the render silhouette in place of the old whole-object detection run, which saves one detector pass per view
  and gives an exact silhouette.

The `whole_object` and `not_found` rules stay the same. Each view also gets a stored mask named `object`, the render
silhouette, so scoring treats it like any part mask. `PartMask.ConceptImageId` points to the view image.

### 6. Scoring: known orientation, `object` first

**Inputs.** The masks come from the view images, and the turnaround rectangle logic is removed.

**Fitting.**

- Orientation is now known, so `score_view` uses no flip, and the flip search is removed.
- The scale is still fitted. The splat has no real-world scale, so each view uses a uniform fit, as now.
- With the shared pixel scale, the four views fit consistently.

**The `object` score.** The `object` mask is compared with the union of all parts. It reports:

- `object_iou`;
- the signed width and height errors per view;
- `mean_object_iou` over all views.

**Agent stop rule.** The build is validated, `mean_object_iou` is at least 0.8, and no view's object IoU is below
0.7. Part scores guide the fixes, but they don't gate. This matches the "looks right" bar.

### 7. Image model bake-off (part of B)

**Candidates:**

- FLUX.2 klein 4B fp8 (installed);
- Qwen-Image-Edit-2511 in ComfyUI's native `fp8mixed` format (20.5 GB), with the fp8 Qwen2.5-VL 7B text encoder
  and the Apache 2.0 Lightning 4-step LoRA. ComfyUI offloads the weights that don't fit in 12 GB to RAM (the machine
  has 64 GB). GGUF Q4 was rejected: it needs a custom node pack (`ComfyUI-GGUF`) and loses quality. GGUF is the
  fallback only if fp8 runs out of memory.

**Procedure.** Both models get the same Gnome-village anchor references, the same prompts (one scene anchor plus the
cart and one house hero) and 2 seeds each. The comparison records:

- time per image;
- peak memory;
- the user's ratings for style match, object correctness and element placement.

The results go into `notes.md` in this change.

**Choosing.** The winner's workflows become `style-anchor` and `hero`; the loser's files are deleted. The choice can
also be split, one model per operation.

Qwen needs about 31 GB of disk for the model, text encoder, VAE and LoRA; you approved the download.

### 8. Agent and UI

**Agent pipeline:** anchor → `create_asset` → `start_job hero` (count 2–3) → **wait** for the pick → `start_job views`
→ `segment-parts` on the hero → the rest unchanged.

**Agent tools.**

- `get_segmentation(heroId)` returns, per view, the image size, the silhouette bounds and the part masks.
- `list_concepts` returns the kinds with `sourceConceptId`.
- When the front was assumed, the agent asks the user to check the views before modelling.

**UI.**

- The Concepts tab has kind groups Anchors / Heroes / Views; the views sit under their hero.
- A picked hero card shows "Make views".
- The hero's concept page shows its four views, front-direction buttons (turn ±90°, flip 180°) that rerun
  `views` with the same seed, and the parts segmentation box.
- The asset list's per-row generate button makes heroes.

### 9. Licences checked before use

Each model's licence must allow commercial use of its outputs before it ships in the README:

- Idol and TripoSplat;
- BiRefNet;
- DINOv3, which has Meta's own licence and must be read;
- Qwen-Image-Edit-2511 and its LoRA;
- SAM 3.1, already in use under the "SAM License", which must also be confirmed.

If one fails, we look for a replacement before continuing; for example, a different background remover.

## Risks / Trade-offs

- **[The splat guesses the hidden back]** → Scoring weights views equally, but the agent works mainly from the front
  and side. The back view is shown to the user for judgement and isn't required to score.
- **[Thin parts (an axle, rope) vanish in the splat]** → `object` scoring tolerates them. The parts appear as missing,
  and the agent sizes them from the manifest, as it does now.
- **[The splat's coordinate frame differs from the assumption]** (the yaw sign, or which way is up) → Task 3.3
  calibrates on a known object: the cart, whose handles point backwards. `QUARTER_SIGN` and the axis map are fixed there
  before scoring work starts.
- **[Qwen at Q4 is too slow, or doesn't fit next to the encoder]** → That is a bake-off outcome, not a blocker. klein
  stays the default.
- **[A DINOv3 or SAM licence forbids commercial use]** → Task 1.1 checks this first, before any implementation, and
  stops the change if the problem can't be solved.
- **[Removing turnarounds deletes data]** → It's local test data only. A git revert plus a database backup
  (`<data-dir>/slopoly.db`) restores it; the migration notes say to back up first.

## Migration Plan

1. Back up `<data-dir>/slopoly.db`.
2. Download the Idol models (and Qwen for the bake-off) into `<models-dir>`.
3. Run the stack; the migration deletes turnarounds.

**Rollback:** a git revert of the change plus restoring the database backup.
