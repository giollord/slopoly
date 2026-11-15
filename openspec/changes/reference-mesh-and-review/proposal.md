# Proposal

## Why

A first complex asset (a steam locomotive with bone decorations, built to 6,000 triangles) showed that the modelling
loop breaks down for busy, long or detailed objects. The views come from fixed turntable frames of a Gaussian splat.
They crop long objects, and their side view disagreed with the front. Text-prompted segmentation returned mostly
noise. Silhouette IoU couldn't see the shape character the user cared about: a V-shaped cowcatcher in plan, bone ends
on top, bent spikes. Most rounds of user feedback were about features that were visible in the hero but never written
down, and the user had to describe them in chat without a way to point at them. The session also hit a handful of CLI
and modelling-API bugs.

## What Changes

- **Reference mesh.** `slopoly gen views` makes a rough 3D mesh of the reference hero with an image-to-3D model on
  the user's ComfyUI (TRELLIS.2 or Pixal3D, from the ComfyUI template `3d_pixal3d_trellis2_image_to_model`, cut down
  to shape and vertex colours). The CLI scales the mesh to the asset's real size and renders the views from it in
  Blender. The views are framed to the object's bounds and use a camera handedness the CLI checks against the hero.
  The default generator is chosen by a recorded benchmark against Idol on the same heroes; Idol, its splat turned
  into a mesh (`idol-mesh`), won and is the default.
  **BREAKING**: views made by the Idol splat turntable are replaced, so existing assets need `gen views` again.
- **Close-ups and measurements.** A new `slopoly look` renders the reference mesh (and optionally the current build)
  from any direction and zoom, so the agent can study a feature's shape. Results give bounds in metres.
- **Better segmentation.** Parts can be segmented within a box or on a zoomed crop. Masks that cover most of the
  object, or share one box with other parts, are flagged as implausible. Masks from several mesh renders are voted
  onto the reference mesh's faces, giving 3D part regions with metric bounds.
- **3D comparison.** Builds are also compared with the reference mesh in 3D (volume overlap and per-region surface
  distance), next to the existing per-view silhouette scores.
- **Review window and notes.** A new `slopoly review` opens a window with the reference (the hero image or the rough
  mesh) beside the build. The user can lock the two cameras together, paint on both panes and add a comment, as many
  times as they like, then send. Each note carries its images, the camera, the build parts the strokes hit (weighted,
  nearest surface only), and the painted region on the reference mesh in metres. Notes are stored per variant with a
  status (`open`, `addressed`, `wontfix`). The next review shows earlier notes again so the user can confirm fixes.
- **Shape plans.** Each manifest part may describe its shape character (`shape`), its construction steps (`steps`)
  and how it will be checked (`checks`). The skill requires them for complex assets and has the agent check them
  against `look` close-ups itself. The user corrects plans through review notes.
- **Stop criterion.** Once the user has reviewed a build, the agent may stop only when the build is validated, it has
  no open notes, and any IoU drop is explained. Notes come before the IoU bar.
- **Fixes from the session notes:**
  - A pick after `gen revise` can replace a variant's reference, and a new `slopoly variant reference` command
    sets a reference while keeping the program and builds.
  - Bad targets get a "did you mean `<pack>/<asset>:<variant>`" hint.
  - `slopoly view` prints its URL.
  - `join` no longer fails on duplicate faces.
  - Two-point curves honour `resolution`.
  - `jitter` limits itself on thin walls and warns about self-intersections.
  - Contact reports give the nearest points.
  - A new `surface_point` helper places parts on curved surfaces.
- **Skill and knowledge:**
  - Heroes show no smoke or particles.
  - Bands are made as profile steps with `paint`, not as unioned rings.
  - The docs say which way a curve's profile axes point.
  - Hero vehicles get a 3,000–6,000 triangle budget.
  - The agent writes programs with file tools, not shell heredocs.
  - New object notes: steam locomotive and bone decorations.

## Capabilities

### New Capabilities

- `reference-mesh`: the rough 3D mesh of a reference hero: its generation, real-size scaling, close-up renders
  (`look`), metric measurements, and the benchmark that picks the generator.
- `review-notes`: the review window, user notes with painted regions and part hits, and the note lifecycle the agent
  works through.

### Modified Capabilities

- `asset-views`: views are rendered from the reference mesh, framed to the object's bounds. The front direction and
  handedness come from the mesh and the hero, and the splat requirement is replaced.
- `image-generation`: segmentation accepts boxes and crops, flags implausible masks and votes masks into 3D regions.
  The hero prompt excludes smoke, steam, fire and particles.
- `part-modeling`: manifests carry shape plans, builds get a 3D comparison against the reference mesh, contact
  reports give nearest points, and `join`, `curve` and `jitter` behave as documented. `surface_point` is added.
- `asset-variants`: a hero can replace a variant's reference while its program and builds are kept.
- `interaction-windows`: the review window is added, and the view command reports its URL.
- `design-agent`: the agent plans part shapes, inspects close-ups, works through review notes, and stops by the new
  criterion.
- `knowledge-base`: the shipped notes gain the techniques and object notes listed above.
- `slopoly-cli`: target errors suggest the right target shape.

## Impact

- **ComfyUI:**
  - A new `reference-mesh` workflow (source, export, recipe), derived from the gallery template.
  - New models in `models.yaml`, each checked to be local and commercially usable: TRELLIS.2 diffusion model and
    VAEs, a DINOv3 encoder, MoGe 2 and Pixal3D.
  - The Idol `views` workflow and its models are removed if the benchmark picks a mesh generator.
- **Code:**
  - `generate.py` and `comfy/views.py`: views from the mesh. Turntable frame picking is removed.
  - `blender/slopoly_model/`: mesh import and scaling, view and close-up renders, 3D comparison, face voting, ray
    casts for review hits, and the `join`, `curve`, `jitter`, contact and `surface_point` changes.
  - `windows/`: a review page with two three.js panes and a paint overlay.
  - `models.py`: manifest plan fields, review notes and reference-mesh metadata.
  - `cli.py`: `look`, `review`, `variant reference`, target hints, and the `view` URL.
- **Skill:** `SKILL.md`, `workflow.md`, `modelling-api.md` and the knowledge notes. Version bump across the four
  version files.
- **Workspaces:** assets get `reference/<hero>/mesh.glb` and per-variant `notes.yaml`. Existing views must be
  regenerated.
- **Host:** more GPU memory and time for views. The benchmark records both.
