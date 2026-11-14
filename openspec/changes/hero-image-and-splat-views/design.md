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

### 2. Two workflows: `views` builds the splat, `render-views` renders it

**`views`** (built with the comfy CLI from the Idol template):

```
in:image -> RemoveBackground(BiRefNet) -> TripoSplat (Idol) -> SPLAT
                                                    +-> SplatToFile3D(spz) -> out:splat
                                                    +-> RenderSplat(ortho, frames=24, 256 px) -> out:turntable_mask
```

**`render-views`:**

```
in:splat (File3DToSplat) + in:yaw -> 4 x CreateCameraInfo(ortho, same distance/zoom) -> RenderSplat 1024 px
    -> out:front / out:side / out:top / out:back (image) + out:*_mask (mask)
```

**How the worker runs them.** It runs `views` and uploads the `.spz` file as the hero's `SplatFileId`. It then picks
the front yaw (decision 3) and runs `render-views`.

**Correcting the front.** This reruns only `render-views` with the user's yaw. That takes seconds, needs no new
sampling, and the splat stays identical.

**Why two workflows.** Separating rendering from generation makes the front correction cheap and deterministic.

**Alternative rejected:** `SplatToMesh` and rendering the mesh in the geometry worker. That loses colour, which part
segmentation needs, and adds a step.

### 3. Front direction from silhouette symmetry

For each of the 24 turntable masks the worker computes the mirror symmetry of the silhouette: the IoU of the mask with
its left-right flip about the mask's bounding-box centre.

- **Front-or-back ambiguity.** The front and back of a symmetric object both score high. Among the local maxima, the
  worker picks the one nearest the yaw the hero faces. That yaw is the constant `HERO_YAW`, the three-quarter angle
  in the prompt, adjusted by the calibration in task 3.3.
- **Asymmetric objects.** If no direction scores at least 0.8, the worker uses `HERO_YAW` alone. The job then reports
  `front: "assumed"`, so the UI and the agent can ask the user to check it.

**View axes** follow the `slopoly_model` conventions:

| View | Camera |
|---|---|
| front | looks from +Z at `yaw` |
| side | looks from +X at `yaw + 90°` |
| top | `pitch = 89°` |
| back | `yaw + 180°` |

All four use orthographic cameras with the same distance and zoom, so every view shares one pixel scale. The job
records that scale as pixels per splat unit.

### 4. Data model

- `ConceptKind` is `Anchor`, `Hero` or `View`.
- `ConceptImage` gains:
  - `View` (front, side, top or back, for views);
  - `SourceConceptId` (a view's hero);
  - `MaskFileId` (a view's silhouette);
  - `SplatFileId` and `FrontYaw` (on heroes).
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
- Qwen-Image-Edit-2511 at Q4 GGUF, with the Qwen2.5-VL text encoder, a Lightning 4-step LoRA if its licence allows
  commercial use, and the `ComfyUI-GGUF` custom node pinned in the Dockerfile.

**Procedure.** Both models get the same Gnome-village anchor references, the same prompts (one scene anchor plus the
cart and one house hero) and 2 seeds each. The comparison records:

- time per image;
- peak memory;
- the user's ratings for style match, object correctness and element placement.

The results go into `notes.md` in this change.

**Choosing.** The winner's workflows become `style-anchor` and `hero`; the loser's files are deleted. The choice can
also be split, one model per operation.

Qwen needs about 12 GB of disk for the model plus its text encoder; you approved the download.

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
  `render-views`, and the parts segmentation box.
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
  calibrates on a known object: the cart, whose handles point backwards. `HERO_YAW` and the axis map are fixed there
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
3. Rebuild the comfyui image (ComfyUI-GGUF).
4. Run the stack; the migration deletes turnarounds.

**Rollback:** a git revert of the change plus restoring the database backup.
