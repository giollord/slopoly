# Workflow in detail

Work through these stages in order. Stop and wait for the user wherever a stage says so. Paths below are relative to
the pack folder `slopoly/<pack>/`.

## 1. Style

Turn the brief into `style.md`:

- `# Instructions`: what the pack is for, the game's camera and scale, and anything every asset shares.
- `# Style`: look, shapes, palette mood and level of detail, short and concrete. Only this section goes into image
  prompts.

Put style reference images the user gives you in `style/`. Set `budget` (triangles per asset) and `shading` in
`pack.yaml` (see `palette-and-shading.md`).

## 2. Style anchors

`slopoly gen anchor <pack> --prompt "<one-paragraph scene with several typical objects of the pack>" --count 2..4`,
then `slopoly wait <job>`. Then run `slopoly pick <pack> --anchors` and **wait** for the user's choice. The job
result has the picked and rejected paths and an optional note. Heroes use up to three picked anchors as style
references.

In every pick window, what the user doesn't pick is rejected: it moves to a `rejected/` folder next to it, which git
ignores. Never use rejected images; `slopoly pick ... --show-rejected` lets the user take one back.

## 3. Asset and hero

1. Create the asset: `slopoly asset new <pack>/<asset> --description "..."`. Add `--budget N` when its kind needs
   another triangle budget than the pack's (see `knowledge/techniques/triangle-budgets.md`).
2. Generate heroes: `slopoly gen hero <pack>/<asset> --count 2..3`, adding `--prompt "<object only>"` to describe it
   more precisely than the asset description. A hero is one image of the asset alone, seen three-quarter from the
   front-left.
3. Have the user choose: `slopoly pick <pack>/<asset> --heroes`, then **wait**. Heroes belong to the asset
   (`assets/<asset>/heroes/`). Each hero the user picks becomes the reference of a variant they name in the window:
   the default variant first, then a new variant per extra pick (the window warns about that). Naming an existing
   variant replaces its reference. The result lists the `variants` with their references; the rest is rejected.

For more options or a change, run `slopoly gen revise <image> --change "add a red roof" --count N`. Leave `--change`
out to get more of the same. Use exactly the count the user asked for.

## 4. Views

`slopoly gen views <pack>/<asset>` builds a 3D splat of the reference hero and renders front, side, top and back
views, all at one scale, each with its silhouette. When the result's `front` is `assumed` (the object isn't
mirror-symmetric), **ask** the user to check that the front view shows the front. If it doesn't, rerun with
`--front-yaw <current front_yaw + 90, 180 or 270>`. New views replace the old ones and their masks.

## 5. Segmentation

Decide the part names: short nouns, without `_L`/`_R`, one name per mirrored pair. Then run
`slopoly segment <pack>/<asset> --parts "a,b,c"` and wait. The result covers each view:

- the image size;
- the silhouette bounds;
- the part masks (bounds, area, measured colours), including a mask named `object` for the view's exact silhouette.

Parts listed as missing (`not_found`, or `whole_object` when the detector returned the whole object) must be sized
from the manifest and their neighbours. The views give proportions, not real sizes: set the dimensions from the
brief and common sense, and use the views for the proportions.

## 6. Palette

Create main palette roles from the measured colours (`slopoly palette add`), rounding them to clean values. Reuse
existing roles where they fit. See `palette-and-shading.md`.

## 7. Knowledge

Before the manifest, search the notes for the asset's kind (an `objects/` note may cover it) and for each notable
feature (for example "spoked wheel", "curved handle", "bark", "old wooden wear"). The notes are in `knowledge/` next
to this file and in the workspace's `slopoly/knowledge/`. Read the matching ones and apply them: an open container
needs a cavity, a rustic style needs wear, and every part is built with the technique its note gives.

## 8. Manifest

Write `assets/<asset>/variants/<variant>/manifest.yaml`:

```yaml
symmetry: [x]
parts:
  - {name: bed, primitive: box}
  - {name: axle, parent: bed, primitive: prism, connections: [{to: bed, type: rotate, axis: x}]}
  - {name: wheel, parent: axle, primitive: prism, mirror: x}
  - {name: handle, parent: bed, primitive: curve, mirror: x}
```

There is exactly one root part, without a parent. Connection types are `fixed`, `rotate` and `slide`. Run
`slopoly check <pack>` after editing.

## 9. Program and build

Write the part program in the variant's `program.py` (`modelling-api.md`), then run
`slopoly build <pack>/<asset>[:<variant>]`. A program error exits with status 2, with `code: program_error` and the
`line`. The result gives:

- `validated` and `validation`: intersections, contacts, disconnected parts, triangles and issues;
- `silhouette`: per view, the `object` score and the part scores, with `render` and `compare` image paths, and
  `detail`: the regions where the model differs from the view (see step 10);
- `colors`, `palette`, `shading`: the unfixed shading defects per part;
- `files`: the model, the Blender file, the report and the program snapshot.

Each build gets the next number and keeps a copy of its program. The variant's current build is the latest
successful one. `slopoly build use <target> <n>` makes build n current again and restores its program to
`program.py`.

## 10. Iterate

Fix any failing validator first: contacts, disconnected parts, the triangle budget, untagged faces,
unknown roles, and parts that are not closed manifold solids (`not_solid`, see `palette-and-shading.md`). Then improve
the silhouette scores. The `object` score of each view (the whole model against the silhouette) comes first; the part
scores show what to fix:

- a negative `width_error` or `height_error` means the model or part is too small;
- `centre_offset` says where a part should move;
- low `iou` with small errors usually means the shape or orientation is wrong.

For every view whose `object` `iou` is below 0.8, open its `compare` image before changing the program. It shows the
reference view, your model rendered from the same direction, and the silhouette difference:

- red is model where the view has none (too big, too long, extra parts);
- blue is view where the model has none (missing or too small parts, wrong curves);
- magenta is where both cover but the colours differ (a band, trim, window or panel the model lacks, or a wrong
  role);
- orange lines are lines in the view (board edges, frames, seams, panel outlines) with no line near them in the
  render.

Change the parts under the red and blue areas with the matching technique note, for example a curved handle or
spoked wheels instead of straight bars and discs.

A good IoU doesn't mean nothing is missing: a thin handle, a dark band or a frame of boards hardly changes it. So read
every view's `detail` too, even when its IoU is high, and open the `compare` image when it lists regions. Each region
is numbered as in the image and has a `kind` (`missing`, `extra`, `colour`, `edge`), a `box` as fractions of the
object's box (x0, y0, x1, y1 from the top left), its `area` (or `length` for lines), the part `masks` it overlaps,
and its colours. `colour_match` is the share of the model's pixels whose colour matches the view. For each large
region, decide whether it is a design feature the model lacks (add the part, panel, band or frame) or a difference
of the splat (lighting, a guessed back side), and say which in your report. Regions repeated in the front and side
views are rarely noise.

The bar is "looks right", not an exact copy. Stop when:

- the build is validated, `mean_object_iou` is at least 0.8, no view's `object` `iou` is below 0.7, and every large
  `detail` region in the front and side views is either fixed or explained; or
- a handful of attempts have not improved it. Then report what blocks you.

Part scores guide the fixes but don't have to reach a target. The back view is the splat's guess of the hidden side,
so trust the front and side views more. When the user should look, run `slopoly view <pack>/<asset>`. The window
reloads by itself when a new build becomes current.

## Variants

An asset has one or more variants (looks, such as "empty" and "loaded"), each with its own folder under
`variants/` holding its manifest, `program.py` and builds. Heroes, with their views and masks, belong to the asset
(`heroes/`, `views/<hero>/`, `masks/<hero>/`); each variant names one of them as its reference. Name, description and
budget belong to the asset. Build a variant's program only against its own reference's views and its own manifest,
and never mix variants. A build that fails with a program error is moved to `builds/rejected/` (git-ignored), and its
number is not reused.

Create a variant only when the user asks for another look, usually by picking several heroes (or generate more
heroes and pick again). `slopoly variant new <pack>/<asset> <name> --from default` copies the manifest and program;
`--hero <image>` makes a hero its reference. `slopoly variant rename`, `slopoly variant default` and
`slopoly rm <pack>/<asset>:<variant>` do the rest.

## Scenes

When the user asks, or the pack's assets are built:

1. Create a scene: `slopoly scene new <pack>/<scene>`.
2. Write its placements in `scenes/<scene>.yaml`:

   ```yaml
   placements:
     - {name: cart_1, asset: cart, at: [0, 0, 0], rot: [0, 30, 0]}
     - {name: well, asset: well, variant: stone, at: [3, 0, 1]}
   builds: {cart: 4}   # optional: a build number per asset or asset:variant; missing means current
   ```

3. Place assets on the ground (y = the asset's min bound at 0; `slopoly status <pack>/<asset>` and build results give
   bounds), a little apart, turned to face sensible directions as in the picked style anchor.
4. Run `slopoly scene build <pack>/scenes/<scene>`. The report lists each placement's bounds, whether it is
   grounded, and overlapping pairs. Fix the overlaps and the placements that are not grounded.
5. `--current` resets every build choice to current. Change build choices only when the user asks.

## Jobs

Generation takes from seconds to minutes. Wait with `slopoly wait <id>`, which returns `pending` after its timeout;
then wait again. If a job fails, read its `error`. A `missing_model` or `missing_node` error is fixed with
`slopoly doctor` (`--fetch` for models), after which you `slopoly retry <id>`. An `orphaned` job lost its process (a
restart): retry it.

## Knowledge notes

The notes are global, shared by every pack. When the user asks for a technique, or a fix worked after several
attempts, record it in the workspace's `slopoly/knowledge/techniques/<kebab-name>.md` (a modelling technique) or
`slopoly/knowledge/objects/<kebab-name>.md` (how to approach a kind of object):

- front matter with `title`, `tags` and `summary`;
- general wording, with no pack names;
- a short slopoly_model example that builds.

Read the note first when updating one. Don't write notes about one-off details. `slopoly check` validates notes.
