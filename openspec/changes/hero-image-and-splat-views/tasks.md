## 1. Licences and models

- [ ] 1.1 Read the licence files of Idol/TripoSplat, BiRefNet, DINOv3, SAM 3.1, Qwen-Image-Edit-2511, its text encoder and any Lightning LoRA, and record in `notes.md` of this change whether each allows commercial use of outputs. Done when every model used has a recorded "commercial OK". If any fails, stop and report to the user.
- [ ] 1.2 Download the Idol models (and the Qwen GGUF, text encoder and LoRA) into `<models-dir>`, and add them with sizes, subfolders and licences to `comfyui/README.md`. Done when the container's `/models/<folder>` endpoints list them and the README has no host paths.
- [ ] 1.3 Add a pinned `ComfyUI-GGUF` to the comfyui Dockerfile. Done when the container restarts and `object_info` lists its GGUF loader.

## 2. Workflows (comfy CLI, templates)

- [ ] 2.1 Build `hero` from `style-anchor` (1024x1024, hero prompt template) with the comfy CLI. Done when a hero job with the Gnome-village anchors produces 2 images with seeds.
- [ ] 2.2 Build `views` from the Idol template: `in:image`, then `out:splat` (spz) and `out:turntable_mask` (24 orthographic frames at 256 px). Done when a CLI run on a stored hero returns both outputs.
- [ ] 2.3 Build `render-views`: `in:splat`, `in:yaw`, then four orthographic cameras at the same distance and zoom, each giving `out:<view>` (image) and `out:<view>_mask` (mask). Done when a CLI run returns 8 outputs and the front and top silhouette widths agree within 2 %.
- [ ] 2.4 Remove the `turnaround` workflow (source, export and recipe references) and update the workflow table in `comfyui/README.md`. Done when a grep for "turnaround" in `comfyui/` finds nothing.

## 3. Comfy worker

- [ ] 3.1 Add a `hero` operation (shared generation path) and a `views` operation. `views` runs `views`, uploads the splat, picks the front yaw by silhouette symmetry (`front: detected|assumed`), runs `render-views`, and returns the view images, masks, yaw and pixel scale. Done when container tests with recorded fixtures cover the symmetry pick, including the asymmetric fallback, and the output shape.
- [ ] 3.2 Accept an explicit `frontYaw` in `views` (re-render only, reusing the hero's splat). Done when a test shows that a given yaw skips the splat build.
- [ ] 3.3 Calibrate on the cart hero: check that the front view looks from +Z (handles pointing away) and the side view from +X, then set `HERO_YAW` and the axis map. Done when the cart's views match the conventions and the result is recorded in `notes.md`.
- [ ] 3.4 Rework `segment-parts` to run per view image with the render silhouette as the whole-object mask, emitting an `object` mask per view. Remove the crop and thirds code. Done when the comfy tests pass on a recorded per-view fixture.

## 4. Data and API

- [ ] 4.1 Change `ConceptKind` to Anchor/Hero/View, add `View`, `SourceConceptId`, `MaskFileId`, `SplatFileId` and `FrontYaw`, and drop `Views`. Write a migration that first deletes turnaround concepts and their masks. Done when the migration applies to a copy of the current database without errors.
- [ ] 4.2 Add the `hero` and `views` generation in `GenerationService`: views require a picked hero; a re-render passes the yaw. Store the result: view concepts linked to the hero (replacing older views), and splat and yaw on the hero. Done when .NET tests cover the hero job inputs, the refusal for an unpicked hero, the stored views, and replacement on re-render.
- [ ] 4.3 Segmentation takes a hero, expanding to its views with their masks. `get_segmentation` returns per-view sizes and silhouette bounds. Deleting a hero cascades to its views and masks; rejecting it hides them. Done when .NET tests cover these.
- [ ] 4.4 Update REST, MCP and descriptions: `start_job` operations `style-anchor|hero|views|segment-parts`, remove turnaround, and `list_concepts` with kinds. Done when the MCP tool test passes and a grep finds no "turnaround" in `Slopoly.*` except migrations.

## 5. Scoring

- [ ] 5.1 In `silhouette`, use a known orientation (no flip search), score masks named `object` against the union of all parts, and report `object_iou` per view and `mean_object_iou`. In `BuildInputsAsync`, take the masks from the picked hero's views, including `object`. Done when the geometry tests pass, including new ones: a model built to match a synthetic silhouette scores `object_iou` above 0.9, and a misplaced small part lowers only its part score.

## 6. UI and agent

- [ ] 6.1 Concepts tab: kind groups Anchors / Heroes / Views (views under their hero), a New dialog with hero, "Make views" on picked heroes, and the asset row's button generating heroes. Done when checked in the browser with small screenshots.
- [ ] 6.2 Concept page: a hero shows its 4 views, front controls (±90°, 180°) and segmentation; a view links to its hero. Done when checked in the browser.
- [ ] 6.3 `agent/CLAUDE.md`: pipeline steps for hero, views and segmentation; the stop rule (mean object IoU at least 0.8, every view at least 0.7); and asking the user when the front was assumed. Update `agent/docs/slopoly_model.md`'s report section. Done when the docs test passes and the text is reviewed.

## 7. Bake-off and cart run (B)

- [ ] 7.1 Build Qwen-Image-Edit-2511 variants of `style-anchor` and `hero` (comfy CLI, GGUF). Run the bake-off (both models, same references and prompts, 2 seeds each), recording time and peak memory. The user rates style, correctness and placement. Record the results and the choice in `notes.md`, make the chosen workflows the defaults, and remove the loser's files. Done when `notes.md` has the table and the decision.
- [ ] 7.2 Cart run through the agent: brief, then anchor pick, hero pick, views, segmentation, palette, manifest, and iteration to a validated build. Record the outcome, timings, final scores and blockers in `notes.md`. Done when the build is validated with mean object IoU at least 0.8, or the blockers are recorded and reported to the user.
- [ ] 7.3 Run all test suites (.NET, worker, comfy, geometry, agent containers). Done when all pass.
