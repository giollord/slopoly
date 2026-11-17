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

1. Create the asset: `slopoly asset new <pack>/<asset> --description "..." --size <size>`.
   - **State the real size** from the brief and common sense: `--size 9` sets the longest dimension to 9 m,
     `--size z=9` the length from back to front, `--size y=2.5` the height. Every view is then in metres.
     `slopoly asset size <pack>/<asset> <size>` changes it later and rescales the views without regenerating them.
   - **Set the budget from the part count** now, not after the first build: count the parts you expect and give
     each its share (a wheel 60-150 triangles, a plank 12, a lathed part 50-200). Add `--budget N` when that total
     differs from the pack's budget. Hero vehicles and machines with dozens of parts need 3,000-6,000 triangles
     (see `knowledge/techniques/triangle-budgets.md`).
2. Generate heroes: `slopoly gen hero <pack>/<asset> --count 2..3`, adding `--prompt "<object only>"` to describe it
   more precisely than the asset description. A hero is one image of the asset alone, seen three-quarter from the
   front-left.
3. Have the user choose: `slopoly pick <pack>/<asset> --heroes`, then **wait**. Heroes belong to the asset
   (`assets/<asset>/heroes/`). Each hero the user picks becomes the reference of a variant they name in the window:
   the default variant first, then a new variant per extra pick (the window warns about that). Naming an existing
   variant replaces its reference. The result lists the `variants` with their references; the rest is rejected.

For more options or a change, run `slopoly gen revise <image> --change "add a red roof" --count N`. Leave `--change`
out to get more of the same. Use exactly the count the user asked for.

When the revised heroes are meant to replace a variant's reference (not to start a new variant), open the pick with
`slopoly pick <pack>/<asset> --heroes --for <variant>`: the window suggests that variant for the first pick, and the
variant keeps its manifest, program and builds. Without a window, `slopoly variant reference
<pack>/<asset>:<variant> <hero>` does the same. Either way, make the new reference's views next
(`slopoly gen views <pack>/<asset>:<variant>`).

## 4. Views

`slopoly gen views <pack>/<asset>` turns the reference hero into a rough 3D **reference mesh** (Idol on the user's
ComfyUI, under a minute) and renders front, side, top and back views of it, each with its silhouette. The
result gives:

- `mesh`: the reference mesh (GLB), placed at the asset's size, standing on the ground (y = 0), its front towards +Z
  and its bounds centred on x = 0 and z = 0. Build the model in the same place: centre its bounds on X and Z, not
  its main part, or every view and `compare3d` scores the offset;
- `size`, `scale` and `front`/`front_yaw`/`mirrored`: how it was placed. With no size stated, it is 1 m long and the
  result says so: state the size (step 3) before modelling;
- per view: `image`, `mask`, `bounds`, `m_per_px` (metres per pixel, the same in every view), `axes` and
  `ground_row` (the pixel row of y = 0).

The views are **metric**: every view shares one scale and none is cropped, so a long object stays long in the side
and top views, and you can measure parts in metres (pixels x `m_per_px`). The build is scored at that scale too, so
a model of the wrong size scores badly instead of being stretched to fit.

View conventions (Y up, the front faces +Z):

| view  | looks from | image right            | image up                 |
|-------|------------|------------------------|--------------------------|
| front | +Z         | +X                     | +Y                       |
| side  | +X         | -Z (front on the left) | +Y                       |
| top   | +Y         | +X                     | -Z (front at the bottom) |
| back  | -Z         | -X                     | +Y                       |

The front is found by matching the mesh to the hero's three-quarter view and by its mirror symmetry. When the result's
`front` is `assumed`, **ask** the user to check that the front view shows the front. If it doesn't, rerun with
`--front-yaw <current front_yaw + 90, 180 or 270>`: this reuses the mesh and takes seconds. New views replace the old
ones and their masks. `--generator trellis2` (or `pixal3d`) tries another image-to-3D model when the mesh is poor.

### Close-ups: `slopoly look`

`slopoly look <pack>/<asset>[:<variant>]` renders the reference mesh from any direction, which shows what the four
views hide (the top of a funnel, the inside of a cab, how ribs end):

- `--from front|back|left|right|side|top|bottom|hero` or `--from <yaw>,<pitch>` (degrees, yaw from the front towards
  +X);
- `--region <part>` frames a part's 3D region from `slopoly segment`, `--box x0,y0,z0,x1,y1,z1` frames a box in
  metres, `--zoom 2` moves closer, `--perspective` uses a perspective camera;
- `--with-build` renders the current build from the same camera (`--build <n>` another build).

The result has the image paths (`reference`, and `build` with `--with-build`), the `camera` and the framed `bounds`
in metres. Example: `slopoly look medieval/cart --region wheel --from 60,10 --zoom 1.5 --with-build`.

## 5. Segmentation

Decide the part names: short nouns, without `_L`/`_R`, one name per mirrored pair. For a busy object (a locomotive,
a machine), use **fewer, coarser names** first (`boiler, cab, chimney, wheels, cowcatcher`), then refine. Run
`slopoly segment <pack>/<asset> --parts "a,b,c"` and wait. The result covers each view:

- the image size, the silhouette bounds and `m_per_px`;
- the part masks (bounds, area, measured colours), including a mask named `object` for the view's exact silhouette;
- `regions`: each part's region on the reference mesh, voted from several renders, with `bounds` in metres,
  `agreement` and `uncertain` (agreement below 0.6). Use these bounds to size and place parts. A region marked
  `implausible` spans most of the object, so it is not that part: `look --region` refuses it; use `--box` instead.

Parts listed as missing (`not_found`, or `whole_object` when the detector returned the whole object) and masks marked
`implausible` (too large, or nearly the same box as another part) are not trusted. Narrow them down:

- `--parts "chimney@side:0.55,0,0.75,0.4"` looks for the part only within a box of one view (fractions of the image,
  or pixels), cropped and enlarged first;
- `--within boiler` looks for the parts only inside another part's masks;
- parts not named again keep their masks, so a second run can fix one part at a time.

When a part still can't be found, size it from its neighbours with `slopoly look` close-ups and the views in metres.

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

Each part can carry a **shape plan**:

```yaml
  - name: smokestack
    parent: boiler
    primitive: outline
    shape: >
      Flared funnel, about 1.4 m tall: a saddle that wraps the boiler, a narrow neck (r 0.35), widening upward
      into a bell, then a rolled rim and a crown of 6 teeth leaning outward.
    steps:
      - outline profile saddle -> neck -> flare -> rim lip, SCREW lathe around Y
      - bands as profile steps, painted iron (not unioned rings)
      - one tooth (cone), ARRAY x6 around Y, rotated 10 degrees outward
    checks: [side, front, "look:top"]
```

- `shape` says what it looks like: the plan shape, the profile, which way it bends, where its ends or knobs are,
  and what it touches.
- `steps` says how you build it, in modelling operations. A steam pipe is "a cylinder, one end scaled down, the end
  face extruded and scaled up a little into a flange", not "a pipe".
- `checks` lists the views (`front`, `side`, `top`, `back`) and `look:<direction>` close-ups (`top`, `hero`, or
  `<yaw>,<pitch>`) that show it is right.

Write a plan for **every part** of an asset with more than about eight parts, and for every distinctive part of a
smaller one, before the first build. Then check each distinctive part's plan against a close-up of its reference
region (`slopoly look <target> --region <part> --from <direction>`) and correct the plan where they disagree: which
way a part bends, where its ends or knobs are, how many teeth or spokes it has. Don't ask the user to approve plans;
they correct them through review notes. After a build, look at the part again with `--with-build` from the same
camera.

## 9. Program and build

Write the part program in the variant's `program.py` (`modelling-api.md`) with your file-editing tools, never with
shell heredocs or `echo` (shells mangle backslashes, quotes and line breaks in Python code). Then run
`slopoly build <pack>/<asset>[:<variant>]`. A program error exits with status 2, with `code: program_error` and the
`line`. The result gives:

- `validated` and `validation`: intersections, contacts, disconnected parts, triangles and issues;
- `silhouette`: per view, the `object` score and the part scores, with `render` and `compare` image paths, and
  `detail`: the regions where the model differs from the view (see step 10);
- `compare3d`: the build against the reference mesh in 3D (see step 10);
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
of the reference mesh (lighting, a guessed back side), and say which in your report. Regions repeated in the front and side
views are rarely noise.

`compare3d` compares the build with the reference mesh in 3D, which catches what no single view shows (a V-shaped
plough built as a flat bar, a missing part behind another):

- `volume_iou`: the overlap of the two solids (0-1);
- `distance`: `mean` and `p90` surface distance in metres, both ways;
- `missing`: regions where the reference has surface the build lacks, each with `bounds` in metres, its `share` of the
  surface and the build `parts` nearby; `extra`: the reverse;
- `inside_build`: reference surfaces inside the build's closed volume (the rough mesh's inner walls), with the
  `parts` that enclose them. They are not missing; ignore them unless the part should be hollow.

Treat a large `missing` or `extra` region like a `detail` region: fix it, or explain it (the reference mesh is rough,
and its hidden sides are guesses).

The bar is "looks right", not an exact copy. Before the user's first review, stop when:

- the build is validated, `mean_object_iou` is at least 0.8, no view's `object` `iou` is below 0.7, and every large
  `detail` and `compare3d` region is either fixed or explained; or
- a handful of attempts have not improved it. Then report what blocks you.

Part scores guide the fixes but don't have to reach a target. The back view is the mesh's guess of the hidden side,
so trust the front and side views more.

## 11. Review

When a build is worth showing (it reaches the bar, or you are stuck), open a review:
`slopoly review <pack>/<asset>[:<variant>]`, then `slopoly wait <job>`. The result has the window's `url`; give it to
the user if no window appeared. In the window the user sees the reference (the hero image, or the rough 3D mesh)
beside the build, locks the cameras, paints over what is wrong on either side and writes a comment, as many notes as
they like, then sends them. The job result lists the notes:

- `number`, `comment` and the pane `images` (open them): the painted area is shown as it was, inside a yellow and
  black border, and the rest is dimmed. The border and the dimming are not part of the design. A pane without paint
  is the plain view;
- `hits`: the build parts under the paint, each with its `share` of the paint and its `centre` in metres;
- `empty`: the share of paint over empty space (something missing), and `region`: the painted bounds on the
  reference mesh, in metres.

**The comment decides; hits are hints.** Paint also covers neighbours and background, so change the part the comment
is about, even when another part has some share. Work through the notes in order. After the build that addresses a
note, run `slopoly note <pack>/<asset>[:<variant>] <number> addressed --by <build> --reason "what you changed"`. A note
you can't fix gets `wontfix` with the reason, and you tell the user. `slopoly notes <target>` lists the open and
addressed notes (`--brief`: only number, status and comment). The next review shows addressed notes for the user to
confirm or reopen; a reopened note comes back `open` with the user's new comment. `slopoly status` counts addressed
notes the user hasn't confirmed yet as `unconfirmed`: they are not done until a review closes them.

If the user closes the window with unsent notes, the window asks whether to send them. A review closed without
sending ends `cancelled`, with no notes.

After a review, stop only when the build is validated, the variant has no open notes (`slopoly status` counts them),
and every IoU drop since the review is explained in your report. A drop caused by a change the user asked for is
explained by naming the note ("side IoU 0.77 -> 0.71: the longer cowcatcher of note 1").

`slopoly view <pack>/<asset>` opens the plain 3D viewer; it reloads by itself when a new build becomes current.

## Variants

An asset has one or more variants (looks, such as "empty" and "loaded"), each with its own folder under
`variants/` holding its manifest, `program.py` and builds. Heroes, with their views and masks, belong to the asset
(`heroes/`, `views/<hero>/`, `masks/<hero>/`); each variant names one of them as its reference. Name, description and
budget belong to the asset. Build a variant's program only against its own reference's views and its own manifest,
and never mix variants. A build that fails with a program error is moved to `builds/rejected/` (git-ignored), and its
number is not reused.

Create a variant only when the user asks for another look, usually by picking several heroes (or generate more
heroes and pick again). `slopoly variant new <pack>/<asset> <name> --from default` copies the manifest and program;
`--hero <image>` makes a hero its reference. `slopoly variant reference <pack>/<asset>:<variant> <hero>` replaces a
variant's reference and keeps its manifest, program and builds (see step 3). `slopoly variant rename`,
`slopoly variant default` and `slopoly rm <pack>/<asset>:<variant>` do the rest. A variant is always one target,
`<pack>/<asset>:<variant>`, never two arguments.

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
