---
title: Organic shapes by deformation
tags: [organic, branch, branches, root, roots, horn, tentacle, tail, bend, bent, taper, curve, natural, deform, group, ramp, simple_deform, cast]
summary: Turn straight primitives into natural forms - add length segments, weight a vertex group with a ramp, then bend and taper it (group transforms or SIMPLE_DEFORM); CAST and DISPLACE for lumps.
---

Natural shapes are straight primitives deformed, not built point by point.

1. **Segments.** A deform needs vertices along the length. A straight `curve` with `smooth=False` and a
   `resolution` gives a pole with that many rings; a box gets them from `bevel` or SUBSURF.
2. **Weights.** `group(shape, "tip", weight=ramp("y"))`: 0 at the base, 1 at the tip.
3. **Deform.** Each vertex moves by its weight:
   - bend: `shape.rotate(z=40, group="tip", about=base)`;
   - taper: `shape.scale(0.4, 1, 0.4, group="tip", about=base)`;
   - or Blender's SIMPLE_DEFORM (BEND, TAPER, TWIST) limited to the group, around an `origin` empty.

```python
pole = curve([(0, 0, 0), (0, 1.0, 0)], ngon(5, r=0.06), resolution=6, smooth=False, tag="bark")
branch = group(pole, "tip", weight=ramp("y"))
branch = branch.rotate(z=35, group="tip").scale(0.35, 1, 0.35, group="tip")
part("branch", branch)

horn = group(cone(6, r=0.08, length=0.5, tag="bone").modify("SUBSURF", levels=1), "curl", weight=ramp("y"))
part("horn", horn.modify("SIMPLE_DEFORM", group="curl", deform_method="BEND", deform_axis="Z", angle=1.2),
     at=(0.5, 0.3, 0))
```

- Bend a little more than the hero shows: flat shading makes curves read straighter.
- Branching: build each branch the same way, then `rotate` and place it on its parent with `overlaps`.
- Lumpy forms (blobs, fruit, heads): SUBSURF `levels=1`, then CAST (`factor` 0.5–1 rounds it) and a light
  DISPLACE with a `texture()`; finish with DECIMATE when over budget.
- Twisted wood or rope: SIMPLE_DEFORM `deform_method="TWIST"` along the length.
- Keep 4–6 sides on thin organic parts; the deform hides the low side count.
