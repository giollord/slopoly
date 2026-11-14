## Why

The 3-view turnaround sheet is the weak link of the pipeline. FLUX.2 klein 4B rarely keeps the front/side/top layout,
so the views often show the wrong angles at different scales. The only cart build scored a mean silhouette IoU of
0.05, which means scoring compared the model against the wrong views and the agent had nothing to converge on. The
image model also puts elements in the wrong places.

The bar for assets is that they "look right": they follow the pack style and fit their scenes. They don't need to
copy a drawing exactly. That bar suits a different source for views: one good, style-referenced hero image per asset,
turned into a 3D Gaussian splat. Orthographic views rendered from the splat agree with each other by construction.
Everything runs locally under commercial-use licences: Idol/TripoSplat is Apache 2.0/MIT and Qwen-Image-Edit-2511 is
Apache 2.0.

## What Changes

- **BREAKING:** Remove the turnaround sheet completely: the `turnaround` workflow and operation, the `Turnaround`
  concept kind, view regions inside one image, and the existing turnaround images (with their masks).
- **Hero images.** A hero is a single three-quarter front view of one asset on a plain background, generated with the
  pack's picked style anchors as references. Users pick, reject, revise and delete heroes like any other concept.
- **Views from a splat.** A `views` job turns a picked hero into a Gaussian splat (Idol) and renders separate front,
  side, top and back images at one shared orthographic scale. The job also stores:
  - each view's exact object silhouette, from the render mask;
  - the front direction and seed, so the same splat can be rebuilt;
  - the proxy's bounding-box proportions. The splat has no real-world scale; the agent sets the size.

  The front direction is found automatically from the splat's mirror symmetry, and the user can correct it.
- **Segmentation on view images.** Part masks are computed per view image. The whole-object mask comes from the
  render, not from the detector.
- **Scoring by look.** Builds are scored per view on the whole-object silhouette (the primary signal) and per part
  (secondary), with a known orientation. The agent stops at a whole-object threshold instead of at a part-IoU target.
- **Image model bake-off.** Compare FLUX.2 klein 4B with Qwen-Image-Edit-2511 (fp8, local) for heroes and style
  anchors on the same references and prompts. The winner becomes the workflow default; workflows stay repository
  files, so switching later is only a file change.
- **Cart run.** Take the cart from a hero to a validated build through the agent, with the user's picks. Record the
  timings, scores and blockers. This replaces the never-run foundation task 11.1.
- UI, agent tools and agent instructions follow the new flow:
  - The Concepts tab groups anchors, heroes and views.
  - A picked hero has a "Make views" action.
  - The concept page shows a hero's views and a front-direction control.

## Capabilities

### New Capabilities

- `asset-views`: hero image to splat to consistent orthographic view images, with silhouettes and front-direction
  detection.

### Modified Capabilities

- `image-generation`:
  - the turnaround requirement is replaced by hero generation;
  - segmentation works on view images;
  - numeric results no longer mention view regions.
- `asset-packs`: concept kinds are anchors, heroes and views. Views belong to their hero.
- `part-modeling`: silhouette scoring targets the view images, with a whole-object score.
- `design-agent`: the cart end-to-end run goes through hero and views.
- `studio-ui`: concept management and the concept page use heroes and views instead of turnarounds.

## Impact

- **ComfyUI workflows:**
  - new `hero` and `views` workflows, built with the comfy CLI from templates (the TripoSplat/Idol template and two
    native `RenderSplat` turntables);
  - `turnaround` removed;
  - `segment-parts` unchanged;
  - possibly Qwen-Image-Edit variants of `style-anchor` and `hero`.
- **Models to download into `<models-dir>`:**
  - Idol: `idol_fp16`, `idol_decoder_fp16`, `dino_v3_vit_h_bf16` and `birefnet`, about 3.3 GB;
  - Qwen-Image-Edit-2511 (fp8mixed), its text encoder, VAE and Lightning LoRA, for the bake-off.

  `comfyui/README.md` lists the models with their licences.
- **Comfy worker:** the `hero` and `views` operations. `views` does the symmetry search over the turntable frames;
  segmentation runs per view image.
- **Data:**
  - `ConceptKind` becomes Anchor, Hero or View;
  - `ConceptImage` gains `View`, `SourceConceptId`, `FrontYaw`, `ViewsSeed` and `MaskFileId`, and drops `Views`;
  - an EF migration deletes the old turnaround concepts and their masks.
- **API and MCP:**
  - generate `hero`;
  - `start_job` operation `views`;
  - `segment-parts` takes a hero (its views);
  - `get_segmentation` and `list_concepts` follow the new kinds;
  - the turnaround paths are removed.
- **Geometry:** silhouette scoring per view image with known orientation, plus an `object` score.
- **UI and agent:** the Concepts tab, concept page and asset list; `agent/CLAUDE.md` pipeline steps 3–4 and 9.
