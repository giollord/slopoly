---
title: Joints and moving parts
tags: [joint, joints, pivot, hinge, hinged, door, lid, chest, wheel, axle, lever, drawer, slide, rotate, moving, animation, origin]
summary: Parts that move are built around their pivot - the shape's origin sits on the hinge or axle - get rotate() or slide() joints, and are children of what they move against.
---

A part rotates or slides around its own origin. So:

1. Build the shape with its pivot at (0, 0, 0): move the shape so the hinge edge or the axle line passes through
   the origin.
2. Place the part with `at=` the pivot's world position.
3. Give it `joint=rotate(axis, limits)` (degrees) or `slide(axis, limits)` (metres).
4. Make it a child of the part it moves against; mirror pairs keep mirrored joints.

```python
body = box(0.8, 0.45, 0.5, tag="wood")
part("chest", inset(body, "top", 0.03, tag="wood inside").modify("BEVEL", width=0.01, limit_method="ANGLE"),
     at=(0, 0.225, 0))
lid = box(0.82, 0.12, 0.52, tag="wood").move(0, 0.06, 0.26)      # hinge along the back top edge: z = 0 at the back
part("lid", lid, parent="chest", at=(0, 0.45, -0.26), joint=rotate("x", limits=(-110, 0)))
drawer = box(0.3, 0.12, 0.45, tag="wood dark").move(0, 0, -0.225)  # slides out of the front
part("drawer", drawer, parent="chest", at=(0.2, 0.12, 0.25), joint=slide("z", limits=(0, 0.3)), overlaps=["chest"])
```

- Wheels: the axle rotates, wheels are its children (see "wheeled-objects"); or each wheel rotates on its own
  `rotate("x")` around its hub.
- Doors: the hinge is a vertical edge; rotate around "y".
- Levers and cranks: the pivot is the end of the lever, not its centre.
- Check in the report's parts list that `origin` is where you expect the pivot.
