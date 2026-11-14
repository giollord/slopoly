# slopoly_model: part program reference

A part program is Python that builds a low-poly model from named parts. The build runs it with every function below
already imported (no `import` needed), then validates, scores and exports it. Submit it with `submit_program`, then
read `get_build_report`.

**Conventions**

- Units are metres, with Y up.
- The front of the object faces +Z, and its left/right are on X. Use `_L` for +X and `_R` for −X.
- The view images (rendered from the hero's splat) map as follows:
  - **front** looks from +Z;
  - **side** looks from +X, with the object's front on the image's left;
  - **top** looks down from +Y, with the front at the bottom;
  - **back** looks from −Z.
- Shapes are centred on their own origin, and `part(..., at=...)` puts that origin at a world position. Build moving
  parts around their pivot.
- Every face needs a palette role, set with `color=` on the part or with `tag=`/`paint` on faces. Roles must exist in
  the pack palette (`get_palette`, `upsert_palette_entries`).
- Keep it low-poly: use small segment counts (6–12 for round parts), and prefer `extrude`/`inset` to `boolean`.

## Example

```python
part("bed", bevel(box(0.8, 0.3, 0.7), 0.02), at=(0, 0.49, 0), color="wood")
part("axle", prism(6, r=0.04, length=1.1, axis="x"), parent="bed", at=(0, 0.3, 0), joint=rotate("x"), color="metal")
wheel = extrude(inset(prism(8, r=0.3, length=0.08, axis="x"), "+x", 0.2, tag="metal"), "metal", 0.03)
part("wheel_L", wheel, parent="axle", at=(0.5, 0.3, 0), color="wood dark", overlaps=["axle"], mirror="x")
handle = sweep([(0, 0, 0), (0, 0, -0.6), (0, 0.1, -0.85)], ngon(6, r=0.03))
part("handle_L", handle, parent="bed", at=(0.3, 0.55, -0.35), color="wood dark", mirror="x")
socket("hitch", at=(0, 0.55, -1.2), parent="bed")
```

## Primitives

| Function | Result |
|---|---|
| `box(width, height, depth, tag=None)` | A box with 6 quads: width along X, height along Y, depth along Z. |
| `prism(n, r, length, axis="y", tag=None)` | A low-poly cylinder: n side quads and two n-gon caps. |
| `cone(n, r, length, axis="y", r2=0.0, tag=None)` | A cone with radius `r` at the negative end and `r2` at the positive end. `r2=0` makes it pointed. |
| `ngon(n, r, axis="y", tag=None)` | A flat n-gon facing `axis`. Use it as a `sweep` profile or as a base to `extrude`. |
| `sweep(path, profile, closed=False, tag=None)` | Sweeps a profile (an `ngon`, or a list of (u, v) points) along a polyline of (x, y, z) points. Corners are mitred, open ends are capped, and `closed=True` makes a ring. |

## Operations

Primitives return a `Shape`. Operations return a new `Shape` and leave their input unchanged, so one shape can serve several parts.

| Function | Result |
|---|---|
| `extrude(shape, faces, distance, tag=None)` | Moves the selected faces along their average normal and adds side quads. A negative distance pushes them in. |
| `inset(shape, faces, thickness, depth=0.0, tag=None)` | Insets the selected faces as one region and adds a rim of quads. `tag` applies to the inner faces, so follow it with `extrude(..., "<tag>", d)` to make a hub or boss. |
| `bevel(shape, width, segments=1, faces=None)` | Bevels the edges of the selected faces, or every edge when `faces` is None. |
| `jitter(shape, amount, seed=0, faces=None)` | Moves each vertex of the selected faces by a seeded random offset of up to `amount` metres per axis, for dents, sag and uneven chips. The shape stays closed. Use 1–3 % of the part's size. |
| `boolean(a, b, op="difference")` | Combines two closed shapes with `"union"`, `"difference"` or `"intersection"`. Coplanar triangles are merged back. Booleans are counted in the report. |
| `join(*shapes)` | One shape made of several shapes. Nothing is merged. |
| `paint(shape, tag, faces=None)` | Sets the palette role of the selected faces. |
| `select(shape, faces)` | Returns the faces a selector matches, for checking a selector. |
| `shape.move(x, y, z)`, `shape.rotate(x, y, z)`, `shape.scale(x, y=None, z=None)` | Transform a shape around its origin. Rotation is in degrees, applied X, then Y, then Z. |

A **face selector** is one of the following:

- `None`/`"all"`: every face.
- A direction (`"top"`, `"bottom"`, `"front"`, `"back"`, `"left"`, `"right"`, `"+x"`, `"-x"`, `"+y"`, `"-y"`,
  `"+z"`, `"-z"`): faces whose normal points that way.
- A tag name.
- A function `(centre, normal) -> bool`.

## Assembly

`part(name, shape, parent=None, at=(0, 0, 0), rot=None, mirror=None, joint=None, color=None, overlaps=())`

Places a shape as a named part. A parent must be defined before its children. Parameters:

- `at`: the world position of the shape's origin.
- `rot`: Euler degrees.
- `mirror="x"`: also creates the exact mirror image across X=0, named with `_L`/`_R` swapped. Its parent is the
  mirrored parent if one exists.
- `joint=rotate(axis)` or `slide(axis)`: the part moves around or along its origin, which is exported as a pivot node.
- `color`: the palette role for faces that have no tag.
- `overlaps`: the parts it may intersect, for example an axle through a wheel.

`instance(name, shape, transforms, parent=None, color=None, overlaps=())`

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
- a selector that matches nothing;
- an unknown or undefined parent;
- a duplicate name.

The build fails with the message and the program line.

## Build report

**validated** is true when all of the following hold:

- no intersection is over 1 % of the smaller part's volume, unless the pair is listed in `overlaps`;
- every child is within 5 mm of its parent;
- every part touches the root's connected group;
- the triangle count is within the pack budget;
- every face has a known palette role.

**parts** lists, for each part: parent, mesh, triangles, booleans, joint, origin, world bounds and program line.

**validation** contains `intersections` (a, b, volume, fraction, allowed, ok), `contacts` (part, parent, gap, ok),
`disconnected`, `triangles` and `issues`.

**silhouette** gives, for each view image that has masks:

- `object`: the whole model against the view's silhouette (the `object` mask): `iou`, `width_error` and
  `height_error`;
- per part mask: the parts it matched, `iou`, `width_error` and `height_error` (signed fractions of the object's size
  in the image; negative means the model is too small) and `centre_offset`;
- `mean_iou` over the view's part masks.

The model is scaled uniformly to the silhouette's size, so the errors show proportions, not absolute size. Over all
views, `mean_object_iou` averages the object scores and `mean_iou` the part scores.

A mask named `wheel` matches the part `wheel`, or else every part whose name starts with `wheel_` (`wheel_L`,
`wheel_front_R`, ...) and every instance of a mesh called `wheel`. Masks
show only visible pixels, so parts that are hidden behind others score low.

**palette** lists the roles in use and the roles missing from the palette.
