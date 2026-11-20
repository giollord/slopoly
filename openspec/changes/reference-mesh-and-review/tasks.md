# Tasks

## 1. Reference mesh workflow and benchmark

- [x] 1.1 Check the licences of TRELLIS.2 (weights and VAEs), `dino_v3_L_naf_fp32`, MoGe 2 and Pixal3D for local
      commercial use, and record them in `notes.md` in this change; verify every candidate kept has a recorded licence
      and source link
- [x] 1.2 Save the gallery template `3d_pixal3d_trellis2_image_to_model` to `comfyui/reference/`, and build
      `comfyui/source/reference-mesh.json` from it with the `comfy` CLI and a new
      `recipes/reference-mesh.recipe.json`. Keep it as cut in design §1, with `in:image`, `in:seed`, `in:generator`,
      `in:resolution`, `in:faces` and `out:mesh`. Verify `./export.sh` writes the API-format workflow and a manual
      `comfy` run on the cart hero produces a GLB
- [x] 1.3 Add the kept models to `src/slopoly/comfy/models.yaml` and the `comfyui/README.md` model and workflow
      tables; verify `slopoly doctor` reports them, and that a missing one fails a job with `missing_model`
- [x] 1.4 Add an Idol candidate (splat → `SplatToMesh` → GLB) for the benchmark. Write a benchmark script under
      `comfyui/` that runs every candidate on the cart, the locomotive and 1–2 more heroes. It records hero-silhouette
      IoU from the hero camera, thin-part survival (judged on renders and noted), time and peak VRAM. Verify it writes
      a results table into `notes.md`
- [x] 1.5 Run the benchmark, choose the default generator and resolution, and record the reasons in `notes.md`;
      verify the shipped workflow's defaults match the choice

## 2. Views from the reference mesh

- [x] 2.1 Add an optional `size` to `asset.yaml` (`models.py`), with `--size` on `asset new`, and validate it in
      `slopoly check`; verify with host tests for valid and invalid sizes
- [x] 2.2 Import the reference GLB and normalise it (host module `meshview`/`reference`, see design §2): Y up, metres, on y = 0, centred,
      size from `size` or estimated and marked `assumed`. Verify with a host test on a fixture mesh
- [x] 2.3 Implement the front and handedness check: hero-camera renders, plain and mirrored, over a yaw sweep, scored
      against the hero, then refined by symmetry. Verify with a host test that a mirrored fixture is mirrored back
      and reported `mirrored: true`
- [x] 2.4 Render the four orthographic views framed to bounds plus margin at one shared metres-per-pixel, with exact
      masks, and store them with the mesh, the scale, the ground row and the image axes in the views metadata. Verify
      the `asset-views` consistent-proportions scenario and a long-object test where nothing is cropped
- [x] 2.5 Change the `views` job in `generate.py` to run `reference-mesh`, then the Blender normalise and render
      steps. Keep `--front-yaw` and add `--generator`. Remove `comfy/views.py` frame picking and `QUARTER_SIGN` (Idol
      stays only if task 1.5 chose it). Verify the existing views job tests pass, updated to use a recorded mesh
      fixture (`comfyui/record_fixture.py`)
- [x] 2.6 Make `silhouette.py` score at the views' metres-per-pixel when it is given, keeping the fit as a fallback,
      and mark the scale used in the report. Verify with a test that a model 10 % too long reports a +0.1 width error
- [x] 2.7 Rescale on a changed `size` without regenerating, and make `slopoly check` report views without a reference
      mesh, with the regenerate hint. Verify both with host tests
- [x] 2.8 Update `workflow.md` step 4 and `modelling-api.md` (view conventions, metric views, `size`); verify the
      documented commands match `slopoly --help`

## 3. Close-ups and measurements

- [x] 3.1 Add `slopoly look` as specified in design §4: direction, yaw and pitch, region, box, zoom, perspective and
      `--with-build`. Renders go to a git-ignored `looks/` folder capped at the newest 50. Verify with a Blender-backed
      test that the result has the paths, the camera and the metric bounds
- [x] 3.2 Document `look` in `SKILL.md` and `workflow.md`; verify a documented example runs on the test workspace

## 4. Segmentation

- [x] 4.1 Add segmentation within a region (`part@view:box` and `--within <part>`), crop and enlarge before upload and
      map back. Verify with a recorded SAM fixture that the mask lands in full-view pixels and is marked
- [x] 4.2 Flag implausible masks (area > 50 % of the object, or box IoU > 0.9 with another part's mask); verify with
      unit tests on synthetic masks
- [x] 4.3 Add 3D voting: extra mesh renders, face-ID projection, majority per face, agreement and uncertain parts.
      Save the regions with the mesh. Verify with a Blender test on a two-part fixture that each part's faces and
      metric bounds are found
- [x] 4.4 Add the no-particles and whole-object wording to `HERO_IMAGE` in `generate.py`; verify with a test on the
      built prompt
- [x] 4.5 Update `workflow.md` step 5 (fewer, coarser part names for busy objects, regions, implausible flags, 3D
      regions); verify the wording names only CLI commands

## 5. 3D comparison

- [x] 5.1 Implement the voxel comparison in the build's Blender run: volume IoU, surface distances, and missing and
      extra components with bounds and nearby parts. Add it to the build report. Verify with a Blender test that a
      box build against a V-shaped fixture lists side regions
- [x] 5.2 Document the `compare3d` report section and how to read it in `workflow.md` step 10; verify with a build of
      the cart that the report matches the docs

## 6. Modelling API fixes

- [x] 6.1 Make `join` robust to duplicate faces and raise a named `ShapeError` otherwise; verify with a Blender test
      that joins jittered, unioned curve ribs
- [x] 6.2 Make two-point `curve` with `smooth=False` honour `resolution`; verify the "straight pole with rings"
      scenario in a Blender test, and fix `organic-shapes.md`
- [x] 6.3 Make `jitter` limit moves to the local thickness and warn on self-intersection; verify the jittered banner
      stays solid in a Blender test
- [x] 6.4 Add the nearest points and the gap to contact issues; verify the floating-cylinder scenario in a Blender
      test
- [x] 6.5 Add `surface_point(shape, origin, direction)`; verify spikes placed on an arched roof have no
      intersections in a Blender test, and document it in `modelling-api.md`
- [x] 6.6 Add the shape plan fields (`shape`, `steps`, `checks`) to `ManifestPart` and validate `checks` in
      `slopoly check`; verify with host tests and document them in `workflow.md` step 8

## 7. Review window and notes

- [x] 7.1 Add the notes model (`notes.yaml` per variant: number, build, comment, camera, images, hits, status,
      history) and `slopoly note <target> <n> <status> --by --reason`. Count open notes in `slopoly status`. Verify
      with host tests
- [x] 7.2 Add the `review` job and server endpoints: load the reference (hero image or mesh) and the build, receive
      notes with images, write `notes/` and `notes.yaml`, cancel on close. Verify with a host test that drives the
      endpoints without a window
- [x] 7.3 Build `review.html`:
      - two panes reusing `viewer3d.js` and an image pane;
      - lock (mesh: shared camera; hero: build snaps to the hero direction);
      - paint, erase and clear canvases that freeze the cameras;
      - comment, add note, and a list of notes to edit or delete;
      - send.

      Verify by running it in the browser fallback on the cart
- [x] 7.4 Compute hits on the host from the page's strokes and camera: centre-weighted stroke pixels, a face-ID
      render (nearest surface only), the 10 % floor, the `empty` share, and the reference mesh region in metres.
      Verify with host tests and a manual check on the locomotive
- [x] 7.5 Show earlier `addressed` notes as pins with confirm and reopen; verify a reopened note returns to `open`
      with its comment in history
- [x] 7.6 Add browser fallback support for `review`, and make `slopoly view` return its address; verify with the
      existing window tests extended to review and view
- [x] 7.7 Document `review` and `note` in `SKILL.md` and `workflow.md`, including that hits are hints and the comment
      decides; verify the wording is agent-neutral

## 8. Variants and CLI fixes

- [x] 8.1 Add `slopoly variant reference <pack>/<asset>:<variant> <hero>` and `pick --heroes --for <variant>`, reusing
      the reference replacement code; verify both `asset-variants` scenarios in host tests
- [x] 8.2 Hint the joined target when a variant target is split over arguments; verify with a CLI test on
      `variant default orcish/locomotive variant_2`
- [x] 8.3 Document both in `workflow.md` (Variants, and step 3 after `gen revise`); verify the commands match `--help`

## 9. Skill guidance and knowledge

- [x] 9.1 Update `SKILL.md` and `workflow.md`:
      - state the asset size;
      - shape plans for complex assets and distinctive parts, checked against `look` close-ups;
      - review after a build worth showing, and work through the notes;
      - the new stop criterion;
      - write `program.py` with file tools, never shell heredocs;
      - set the budget from the part count at the start.

      Verify `SKILL.md` names only CLI commands
- [x] 9.2 Add or extend the technique notes:
      - bands as profile steps with `paint` (in `lathed-shapes.md`);
      - curved sheets and which way a curve's profile axes point (in `curved-parts.md` or `thin-shells-and-panels.md`);
      - tapered, bent horns, spikes and tusks (`horn_shape`);
      - safe jitter on thin walls (in `wear-and-imperfections.md`);
      - `join` and boolean triangle costs (in `repeats.md` and `triangle-budgets.md`);
      - hero vehicles and machines at 3,000–6,000 triangles.

      Verify every sample builds with the notes test
- [x] 9.3 Add object notes `steam-locomotive.md` and `bone-decorations.md`, with runnable samples; verify they build
      and are found by searches for "locomotive", "cowcatcher", "bone" and "rib"
- [x] 9.4 Bump the version in `pyproject.toml`, `plugin/.claude-plugin/plugin.json`, `.claude-plugin/marketplace.json`
      and `SKILL.md`; verify `tests/test_versions.py` passes

## 10. End-to-end check

- [ ] 10.1 Rerun the locomotive with the new pipeline. Verify that the side and top views aren't cropped, that the
      front and side agree, that a review round with at least three painted notes reaches the agent with sensible
      hits, and that the agent stops on the new criterion. Record timings and blockers in `notes.md`
- [ ] 10.2 Rerun the cart end-to-end; verify the `design-agent` "Cart end-to-end" scenario still holds with metric
      views, and that `uv run pytest` and `uv run slopoly dev test-blender` pass

## 11. Fixes from the locomotive rerun

- [x] 11.1 Replace Qwen-Image-Edit-2511 in `style-anchor` and `hero` with Mage-Flow-Edit Turbo (Microsoft, MIT,
      July 2026, 4 steps, up to 3 references), built with the `comfy` CLI from the gallery template
      `image_mage_flow_edit_turbo_int8` and a new `recipes/mage-flow-references.recipe.json`. Keep the inputs
      (`prompt`, `seed`, `reference_1..3`, `use_reference_1..3`) and `out:image`. Update `models.yaml`, the ComfyUI
      README, `comfyui-setup.md` and the doctor hint; record the licence check and timings in `notes.md`. Verify a hero
      and an anchor job run on the local ComfyUI and are faster than Qwen
- [x] 11.2 Review window: a light/dark theme switch kept in the prefs, and a see-through brush (strokes drawn opaque
      on the ink canvas, the canvas shown at low opacity so overlaps don't build up). Verify in the browser fallback
- [x] 11.3 Note images: the page sends the panes without ink, and the host draws the highlight: the painted area as
      in the original, a semi-transparent two-tone border around it, the rest dimmed, nothing blurred; a pane without
      strokes is stored unchanged. Verify with host tests
- [x] 11.4 Closing the review with unsent notes, a comment or strokes in progress, or verdicts on earlier notes asks
      to send, close without sending, or cancel (native window: the closing event; browser: the page's leave
      prompt). Add an "All fixed" button for the earlier notes. Verify the endpoints with host tests and the dialog
      in the browser
- [x] 11.5 Packaging: a test that the built wheel contains `static/three/build/three.module.min.js`; `slopoly doctor`
      checks the window files; the view, pick and review pages show an error instead of "Loading..." when a script
      fails to load. Verify with host tests
- [x] 11.6 Workspace version: record the newest CLI version that used a workspace in `slopoly/.slopoly-version`, and
      turn a file with unknown fields written by a newer CLI into a `version_mismatch` error with an upgrade hint.
      Verify with host tests
- [x] 11.7 Jobs: retry a failed `os.replace` on Windows `PermissionError` with a short back-off; `slopoly retry`
      supports every job kind. Verify with host tests
- [x] 11.8 Build results: one triangle count (the validator's), an `over_budget` issue when it fails, and a compact
      `parts` summary (name, triangles, booleans, warnings) in the CLI result. A `not_solid` part that used `jitter`
      names it as the likely cause. Verify with host and Blender tests
- [x] 11.9 `compare3d`: a missing region inside the build's closed volume is marked `inside_build` with the parts
      that enclose it, and doesn't count towards the missing share. Verify with a host test
- [x] 11.10 Segmentation: a 3D region spanning most of the object is flagged implausible and gets no bounds for
      `look --region`. Verify with a unit test
- [x] 11.11 CLI and status: `slopoly notes --brief`; `slopoly status` reports `unconfirmed` (addressed, not yet
      confirmed) notes. Verify with host tests
- [x] 11.12 Docs and knowledge: spoked wheels as a hub prism with extruded spokes and a separate rim
      (`wheeled-objects.md`), torn cloth and ragged edges without booleans, the build report shapes and the
      installation note about closing windows first. Verify the samples build with the notes test
- [x] 11.13 Bump the version to 0.2.1 in the four version files; verify `tests/test_versions.py` and the whole suite
      pass
- [x] 11.14 Replace Mage-Flow-Edit Turbo in `style-anchor` and `hero` with Krea 2 Turbo (int8, 8 steps): plain text to
      image without references, and Krea's style-reference LoRA (`TextEncodeQwenImageEditPlus`, after the gallery
      template `image_krea2_turbo_int8_image_style_reference`) when a job has references; a new
      `recipes/krea2-references.recipe.json`. Add the fallback `style-anchor.z-image-turbo` and
      `hero.z-image-turbo` (Z-Image Turbo, int8, 8 steps, text only, after `image_z_image_turbo_int8`), chosen with
      the new setting `images.model` (`krea2` default, `z-image-turbo`); `doctor` checks and fetches only the selected
      model's files. Drop the empty canvas and `use_canvas`; `gen revise` regenerates with a fresh seed, its source
      as first reference when a change is given. Name Krea's licence limits (commercial use only under $1M yearly
      revenue, content filtering) in the README, `comfyui-setup.md` and `doctor`. Record the comparison in
      `notes.md`. Verify an anchor and a hero job on the local ComfyUI with each model, and the host tests

## Workflow follow-up

- Archive the change after review, and sync the delta specs into `openspec/specs/`.
