---
title: Organic shapes by deformation
tags: [organic, branch, branches, root, roots, horn, horns, spike, spikes, tusk, tusks, claw, fang, thorn, tentacle, tail, bend, bent, taper, curve, natural, deform, group, ramp, simple_deform, cast]
summary: Turn straight primitives into natural forms - add length segments, weight a vertex group with a ramp, then bend and taper it (group transforms or SIMPLE_DEFORM); CAST and DISPLACE for lumps.
---

Natural shapes are straight primitives deformed, not built point by point.

1. **Segments.** A deform needs vertices along the length. A straight `curve` with `smooth=False` and a
   `resolution` gives a pole with that many segments between each two points (a ring of vertices at each); a box gets them from `bevel` or SUBSURF.
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

**Horns, spikes and tusks.** One helper makes all three: a segmented pole tapered by a ramp group, then bent by a
rotation weighted by the same group, so the base stays round and straight and the curl grows towards the tip. A spike is the same with no curl; a tusk has a slight curl and fewer sides.

```python
def horn_shape(length, r, curl=40, sides=6, tag="bone"):
    """A horn along +Y from its base at the origin, tapered to 15 % and its tip turned `curl` degrees towards +Z."""
    pole = curve([(0, 0, 0), (0, length, 0)], ngon(sides, r=r), resolution=8, smooth=False, tag=tag)
    pole = group(pole, "tip", weight=ramp("y")).scale(0.15, 1, 0.15, group="tip")
    return pole.rotate(x=curl, group="tip") if curl else pole


part("head", bevel(box(0.3, 0.25, 0.35, tag="hide"), 0.03))
part("horn_L", horn_shape(0.45, 0.06, curl=50).rotate(z=-35), parent="head", at=(0.12, 0.08, 0),
     overlaps=["head"], mirror="x")
part("spike", horn_shape(0.2, 0.035, curl=0, sides=5), parent="head", at=(0, 0.1, -0.05), overlaps=["head"])
```

- Taper to 10–20 %, not to a point: a zero-width tip makes degenerate faces.
- Read the curl's direction and the tip's position from a close-up (`slopoly look --region horn`) and write them in
  the shape plan before building; horns are easy to curl the wrong way.
- 5–6 sides and 6–8 rings are enough for game horns (60–100 triangles each).
