# slopoly_model: part program reference

A part program is Python that builds a low-poly model from named parts. The build runs it with every function below
already imported (no `import` needed), then validates, scores and exports it. Write it to the variant's `program.py`,
then run `slopoly build <pack>/<asset>[:<variant>]` and read its result.

**Conventions**

- Units are metres, with Y up.
- The front of the object faces +Z, and its left/right are on X. Use `_L` for +X and `_R` for −X.
- The view images (rendered from the reference mesh, at the asset's real size) map as follows:
  - **front** looks from +Z, image right is +X;
  - **side** looks from +X, with the object's front on the image's left (image right is −Z);
  - **top** looks down from +Y, with the front at the bottom (image right is +X);
  - **back** looks from −Z, image right is −X.
- The views are metric: they share one scale, given as `m_per_px` with each view, and `ground_row` is the pixel row
  of y = 0. The views are centred on the object's bounds, so centre the model's bounds on x = 0 and z = 0 (not
  its root part) and stand it on y = 0. A part 120 px wide in a view with `m_per_px` 0.01 is 1.2 m wide. Model at that size; segmentation
  `regions` and `slopoly look` give part bounds in metres directly.
- Shapes are centred on their own origin, and `part(..., at=...)` puts that origin at a world position. Build moving
  parts around their pivot.
- Every face needs a palette role, set with `color=` on the part or with `tag=`/`paint` on faces. Roles must exist in
  the pack palette (`slopoly palette show <pack>`, `slopoly palette add`).
- Keep it low-poly: use small segment counts (6–12 for round parts), and prefer `extrude`/`inset` to `boolean`.
- Model with Blender's tools, not vertex by vertex: primitives, then modifiers (`shape.modify`), vertex groups,
  cloning (ARRAY, MIRROR, `instance`) and booleans. Place points by hand only for 2D profiles and curve control
  points. Search the technique notes (`knowledge/` next to this file, and the workspace's `slopoly/knowledge/`) first.

## Example

```python
part("bed", bevel(box(0.8, 0.3, 0.7), 0.02), at=(0, 0.49, 0), color="wood")
part("axle", prism(6, r=0.04, length=1.1, axis="x"), parent="bed", at=(0, 0.3, 0), joint=rotate("x"), color="metal")
rim = curve(path([(0.28, 0, 0), (0, 0.28, 0), (-0.28, 0, 0), (0, -0.28, 0)], closed=True), ngon(6, r=0.025),
           resolution=3)
spoke = box(0.03, 0.28, 0.03).move(y=0.14)
spokes = spoke.modify("ARRAY", count=6, use_relative_offset=False, use_object_offset=True,
                      offset_object=empty(rot=(0, 0, 60)))
wheel = boolean(boolean(rim, spokes, op="union"), prism(8, r=0.05, length=0.08, axis="z", tag="metal"),
                op="union").rotate(y=90)
part("wheel_L", wheel, parent="axle", at=(0.5, 0.3, 0), color="wood dark", overlaps=["axle"], mirror="x")
handle = curve([(0, 0, 0), (0, 0.02, -0.5), (0, 0.12, -0.85)], ngon(6, r=0.03), resolution=3)
part("handle_L", handle, parent="bed", at=(0.3, 0.55, -0.35), color="wood dark", mirror="x")
socket("hitch", at=(0, 0.55, -1.2), parent="bed")
```

## Primitives

| Function | Result |
|---|---|
| `box(width, height, depth, tag=None)` | A box with 6 quads: width along X, height along Y, depth along Z. |
| `prism(n, r, length, axis="y", tag=None)` | A low-poly cylinder: n side quads and two n-gon caps. |
| `cone(n, r, length, axis="y", r2=0.0, tag=None)` | A cone with radius `r` at the negative end and `r2` at the positive end. `r2=0` makes it pointed. |
| `ngon(n, r, axis="y", tag=None)` | A flat n-gon facing `axis`. Use it as a `curve` profile, or as a base to `extrude` or thicken with SOLIDIFY. |
| `curve(points, profile, resolution=None, smooth=True, closed=False, tag=None)` | A tube along a Blender curve through the (x, y, z) `points` (or a `path()`), with cross-section `profile` (an `ngon`, or a list of (u, v) points). `resolution` is the number of segments between two control points (default 4 when smooth, 1 when straight); `smooth=False` makes straight segments with sharp corners, each split into `resolution` rings, so a two-point pole with `resolution=8` can be tapered and bent with a `ramp` group. The profile's u lies in the plane of the path's bend and v along its binormal: an arc in XY with a profile of u ±0.05, v ±1 is an arched slab 0.1 thick and 2 deep along Z (a curved roof or sheet). Open ends get flat caps; `closed=True` makes a ring. For handles, arches, rims, ropes, horns. |
| `path(points, smooth=True, closed=False)` | Control points of a curve, for `curve` or a CURVE modifier's `object` (bending a shape along it). |
| `outline(points, closed=False, tag=None)` | Connected edges through (x, y) or (x, y, z) points, with no faces. Turn it with SCREW to lathe a round object around Y (x is the radius, y the height): vases, barrels, bottles, columns. |

## Operations

Primitives return a `Shape`. Operations return a new `Shape` and leave their input unchanged, so one shape can serve several parts.

| Function | Result |
|---|---|
| `extrude(shape, faces, distance, tag=None)` | Moves the selected faces along their average normal and adds side quads. A negative distance pushes them in. |
| `inset(shape, faces, thickness, depth=0.0, tag=None)` | Insets the selected faces as one region and adds a rim of quads. `tag` applies to the inner faces, so follow it with `extrude(..., "<tag>", d)` to make a hub or boss. |
| `bevel(shape, width, segments=1, faces=None, angle=30)` | Bevels the edges of the selected faces (every edge when `faces` is None) where the faces meet at `angle` degrees or more, so seams and the soft edges of round parts are left alone. Widths are clamped where bevels would overlap, and bent bevel faces are triangulated. Raises an error instead of returning a broken mesh (non-manifold edges, or vertices pushed outside the shape). Bevel last: after inset, extrude and boolean. |
| `jitter(shape, amount, seed=0, faces=None)` | Moves each vertex of the selected faces by a seeded random offset of up to `amount` metres per axis, for dents, sag and uneven chips. The shape stays closed. Each move is limited to under half the wall behind the vertex, so thin cloth and window pillars don't pass through themselves; a jitter that still makes the shape cut through itself adds a warning to the part's `warnings`. Use 1–3 % of the part's size, and jitter after booleans, not before. |
| `boolean(a, b, op="difference")` | Combines two closed shapes with `"union"`, `"difference"` or `"intersection"`. Coplanar triangles are merged back, and merged faces that aren't flat are triangulated. Booleans are counted in the report. Use `"union"` to combine overlapping solids into one part. |
| `join(*shapes)` | One shape made of several shapes. Nothing is merged, so only join shapes that don't overlap or touch (a joined overlap fails validation as `selfIntersecting`). Faces that repeat another face's vertices, or have fewer than 3 distinct vertices (leftovers of booleans), are dropped. |
| `surface_point(shape, origin, direction=(0, -1, 0))` | Where a ray from `origin` along `direction` first meets `shape`: `(point, normal)` in the shape's own coordinates. Raises an error when the ray misses. Use it to stand studs, spikes and trims on curved surfaces exactly, for example by casting down onto an arched roof, instead of guessing the height. |
| `paint(shape, tag, faces=None)` | Sets the palette role of the selected faces. |
| `select(shape, faces)` | Returns the faces a selector matches, for checking a selector. |
| `shape.move(x, y, z)`, `shape.rotate(x, y, z)`, `shape.scale(x, y=None, z=None)` | Transform a shape around its origin. Rotation is in degrees, applied X, then Y, then Z. |

A **face selector** is one of the following:

- `None`/`"all"`: every face.
- A direction (`"top"`, `"bottom"`, `"front"`, `"back"`, `"left"`, `"right"`, `"+x"`, `"-x"`, `"+y"`, `"-y"`,
  `"+z"`, `"-z"`): faces whose normal is within 30° of that direction (so a 45° bevel face is not "top").
- A tag name.
- A function `(centre, normal) -> bool`.

## Modifiers, vertex groups and raw operations

`shape.modify(type, group=None, **settings)` adds a Blender modifier and returns a new shape. `type` and the settings
are Blender's own (see the Blender manual's modifier pages; settings are the Python property names, such as
`count`, `thickness`, `deform_method`). Axes are program axes (Y up). The stack is applied when the shape is used, so
change a setting and rebuild instead of editing vertices. Modifiers keep the faces' palette tags.

Allowed types are listed in `MODIFIERS`: ARRAY, BEVEL, BOOLEAN, CAST, CURVE, DECIMATE, DISPLACE, EDGE_SPLIT, MIRROR,
SCREW, SHRINKWRAP, SIMPLE_DEFORM, SMOOTH, SOLIDIFY, SUBSURF, TRIANGULATE, WAVE, WELD, WIREFRAME. Settings that need an
object take:

- a shape (BOOLEAN `object`, SHRINKWRAP `target`);
- `empty(at=(0, 0, 0), rot=None, scale=None)`: an empty, for ARRAY `offset_object` (a radial array: `count=n`,
  `use_relative_offset=False`, `use_object_offset=True`, `offset_object=empty(rot=(0, 0, 360 / n))` around Z) or a
  deform `origin`;
- `path(...)`: for CURVE `object`;
- `texture(kind="CLOUDS", **settings)`: a Blender procedural texture for DISPLACE or WAVE `texture`
  (e.g. `noise_scale=0.3`).

Use the viewport settings: `steps` for SCREW, `levels` for SUBSURF. Watch the triangle count: SUBSURF and SCREW
multiply it.

`group(shape, name, faces=None, where=None, weight=1.0)` adds a vertex group: the vertices of the selected faces (all
when `faces` is None) for which `where(x, y, z)` is true, with `weight` a number, a function of (x, y, z), or
`ramp(axis="y", start=0.0, end=1.0, lo=None, hi=None)`, weights that go from `start` to `end` along the axis
(between `lo` and `hi`, by default the grouped vertices' extent). Use groups to:

- limit a modifier: `shape.modify("SIMPLE_DEFORM", group="tip", deform_method="BEND", angle=0.6)`;
- transform part of a shape, each vertex moving by its weight: `shape.move(..., group=)`,
  `shape.rotate(..., group=, about=(x, y, z))`, `shape.scale(..., group=, about=(x, y, z))`. A ramp group rotated
  about the base bends a box into a branch; scaled, it tapers.

Raw Blender operations: `bmesh`, `Vector`, `Matrix` and `math` are available, and `shape.bm` is the shape's
bmesh (modifiers applied), so `bmesh.ops.*` can change it in place. New faces copy the tags of the faces they come
from; faces made from nothing (`bm.faces.new`) have no tag, which fails validation until painted. Prefer a modifier
or a library operation when one does the job.

## Shading

The pack sets the shading of every build (`pack.yaml`: `shading.mode`, `shading.hard_edge_angle`,
`shading.shade_strength`); the user or the agent changes it there.

- **Flat:** every edge is hard; each face shows one shade.
- **Smooth:** normals are shared across edges, so round parts shade round; edges whose faces meet at more than
  `hardEdgeAngle` degrees (60 by default: 6–12-sided parts are smooth, box corners hard) stay hard. Palette
  boundaries never show as hard edges.

Overrides, for smooth packs:

- `sharp(shape, faces=None, border=True)`: keeps the outline of the selected faces hard (`border=False`: all their
  edges), for a crisp rim, a seam or a cut edge.
- `smooth(shape, faces=None)`: shades all edges of the selected faces smooth even past the angle (a cushion, a
  rounded box, a blob).
- `part(..., shading="flat")` or `"smooth"` overrides the pack's mode for one part (a faceted crystal on a smooth
  rock).

## Assembly

`part(name, shape, parent=None, at=(0, 0, 0), rot=None, mirror=None, joint=None, color=None, overlaps=(), shading=None)`

Places a shape as a named part. A parent must be defined before its children. Parameters:

- `at`: the world position of the shape's origin.
- `rot`: Euler degrees.
- `mirror="x"`: also creates the exact mirror image across X=0, named with `_L`/`_R` swapped. Its parent is the
  mirrored parent if one exists.
- `joint=rotate(axis)` or `slide(axis)`: the part moves around or along its origin, which is exported as a pivot node.
- `color`: the palette role for faces that have no tag.
- `overlaps`: the parts it is meant to intersect, for example an axle through a wheel. Overlaps between parts never
  fail validation; listing them marks the ones you meant, so the others stand out in the report.
- `shading`: `"flat"` or `"smooth"` to override the pack's shading for this part.

`instance(name, shape, transforms, parent=None, color=None, overlaps=(), shading=None)`

Places one shape many times as `name_1`..`name_N`, sharing one mesh. Each transform is either `(x, y, z)` or
`{"at": (x, y, z), "rot": (x, y, z)}`.

`socket(name, at, parent=None)`

Adds a named connection point, exported as an empty node `socket_<name>`.

`rotate(axis="y", limits=None)` and `slide(axis="y", limits=None)`

Joints. `axis` is `"x"`, `"y"` or `"z"` (optionally with a sign), or a vector. `limits` are (min, max), in degrees
for `rotate` and in metres for `slide`.

`gradient(role, axis="y")`

Use a gradient palette role along `axis`, as a `color` or a tag. The gradient spans the part, or the faces with that
tag.

## Errors

`ShapeError` and `ModelError` are raised for bad arguments, for example:

- a segment count under 3;
- an unknown modifier type or setting (the message lists the valid ones);
- a selector that matches nothing;
- an unknown or undefined parent;
- a duplicate name.

The build fails with the message and the program line.

## Build report

**validated** is true when all of the following hold:

- every child is within 5 mm of its parent;
- every part touches the root's connected group;
- the triangle count of the exported model is within the pack budget (otherwise the issue `over_budget`);
- every face has a known palette role;
- every part's mesh is a closed manifold solid that doesn't cut through itself (see `palette-and-shading.md`). To
  combine overlapping solids into one part, use `boolean(..., op="union")`, not `join`; or make them separate
  parts, which may overlap. A part that cuts through itself after `jitter` gets a `likely_cause` naming it.

The `slopoly build` result and `report.json` differ in size, not in meaning. The result gives `triangles` (the count
the budget check uses, the same as `validation.triangles.count`), `parts` (name, triangles, and booleans and warnings
when there are any), `validation`, `silhouette` (`views`, `mean_iou`, `mean_object_iou`) and `compare3d`, plus the
file paths. `report.json` holds everything below.

**parts** lists, for each part: parent, mesh, triangles, booleans, warnings (such as a `jitter` that made the shape
cut through itself), joint, origin, world bounds and program line. Booleans re-triangulate the faces they merge, so
a part with booleans often costs far more than its pieces: see the notes on wheels and torn cloth for cheaper ways.

**validation** contains `intersections` (a, b, volume, fraction, allowed, ok; for information: an unlisted
overlap over 1 % has ok false, which is worth a look but doesn't fail the build), `contacts` (part, parent, gap, ok;
a contact that isn't ok also gives the `nearest` point on the part and the `parent_nearest` point on its parent, so
you know which way to move it), `disconnected`, `triangles` and `issues`.

**silhouette** gives, for each view image that has masks:

- `object`: the whole model against the view's silhouette (the `object` mask): `iou`, `width_error` and
  `height_error`;
- per part mask: the parts it matched, `iou`, `width_error` and `height_error` (signed fractions of the object's size
  in the image; negative means the model is too small) and `centre_offset`;
- `mean_iou` over the view's part masks.

With metric views (`"scaling": "metric"` on each view), the model is placed with the view's own metres-per-pixel and
ground row, not stretched to fit: a model that is too small or too long scores badly, and `width_error`/
`height_error` give the size error directly. Old views without a scale are fitted uniformly to the silhouette
(`"scaling": "fitted"`), so their errors show proportions only. Over all views, `mean_object_iou` averages the object
scores and `mean_iou` the part scores.

A mask named `wheel` matches the part `wheel`, or else every part whose name starts with `wheel_` (`wheel_L`,
`wheel_front_R`, ...) and every instance of a mesh called `wheel`. Masks
show only visible pixels, so parts that are hidden behind others score low.

**palette** lists the roles in use and the roles missing from the palette.
