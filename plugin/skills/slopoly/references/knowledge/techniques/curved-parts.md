---
title: Curved and bent parts
tags: [curve, curved, bent, bend, handle, handles, arch, arches, pipe, rail, ring, hoop, hook, frame, path, sweep]
summary: Tubes and bars along Blender curves through a few control points (handles, arches, rails, hoops), and bending an existing shape along a path with the CURVE modifier.
---

**Curve through points.** `curve(points, profile, resolution)` builds a smooth Blender curve through the control
points (auto handles) with `profile` as its cross-section. `resolution` is the number of segments between two
points: 3 points with `resolution=4` give 8 segments.

- `smooth=False`: straight segments with sharp corners (frames, bent wire).
- `closed=True` (or `path(..., closed=True)`): rings and hoops, no caps.
- Profiles: `ngon(4–8, r)` for round bars, a list of (u, v) points for flat or square ones.

```python
handle = curve([(0, 0, 0), (0, 0.03, -0.45), (0, 0.15, -0.8)], ngon(6, r=0.03), resolution=3, tag="wood dark")
part("handle_L", handle, at=(0.35, 0.6, -0.5), mirror="x")

arch = curve([(-0.5, 0, 0), (-0.35, 0.45, 0), (0, 0.6, 0), (0.35, 0.45, 0), (0.5, 0, 0)],
             [(-0.06, -0.08), (0.06, -0.08), (0.06, 0.08), (-0.06, 0.08)], resolution=2, tag="stone")
part("arch", arch, at=(0, 0, 1.5))
```

**Bend an existing shape** (a plank, a blade, a roof sheet) along a path with the CURVE modifier. The shape needs
segments along its length (a straight `curve`, or `bevel`), and lies along the deform axis from the origin:

```python
plank = curve([(0, 0, 0), (0, 1.2, 0)], [(-0.08, -0.01), (0.08, -0.01), (0.08, 0.01), (-0.08, 0.01)],
              resolution=8, smooth=False, tag="wood")
bent = plank.modify("CURVE", object=path([(0, 0, 0), (0.25, 0.6, 0), (0, 1.2, 0)]), deform_axis="POS_Y")
part("rib", bent, at=(0, 0, -1.5))
```

- Keep control points few (3–5): they set the shape; resolution sets the smoothness.
- Compare the side view's silhouette with the comparison image: straight bars against a curved reference show as
  a red/blue band along the handle.
- Handles of a cart: start at the bed, curve slightly down then up to the grip.
