---
title: Repeats - array, radial array, mirror and instances
tags: [repeat, repeats, array, radial, mirror, symmetry, symmetric, clone, cloning, copies, fence, pickets, steps, stairs, columns, bolts, instance]
summary: When to clone with an ARRAY (linear or radial, one mesh), mirror with MIRROR inside a part or mirror= across parts, and when to use instance() for separate parts that share a mesh.
---

| Need | Use |
|---|---|
| Identical pieces in a row inside one part (pickets, steps, bolts, planks) | ARRAY with `relative_offset_displace` or `constant_offset_displace` |
| Pieces around an axis inside one part (spokes, petals, teeth) | ARRAY with `offset_object=empty(rot=...)` |
| A symmetric shape built as one half | MIRROR (`use_axis`, `use_bisect_axis` to cut the half at the mirror plane, merged at the seam) |
| A left/right pair of separate parts (wheels, arms, handles) | `part(..., mirror="x")` |
| Many separate parts sharing one mesh (posts, barrels on a shelf, tiles) | `instance(name, shape, transforms)` |

Copies that overlap inside one part (spokes meeting at the centre, petals) make its mesh cut through itself, which
fails validation (`selfIntersecting`). Keep the copies apart from each other and union the array with the piece they
meet in, for example `boolean(hub, spokes, op="union")`. Copies overlapping each other in the same plane (wide flat
petals) can break the union; make them narrower or thicker.

```python
picket = cone(4, r=0.03, length=0.1, tag="wood").move(y=0.45)
picket = boolean(box(0.06, 0.8, 0.02, tag="wood"), picket, op="union")
fence = picket.modify("ARRAY", count=8, relative_offset_displace=(1.8, 0, 0))
part("fence", fence)

petal = box(0.05, 0.02, 0.2, tag="petal").move(z=0.145)   # narrow enough that the copies only meet in the hub
petals = petal.modify("ARRAY", count=5, use_relative_offset=False, use_object_offset=True,
                      offset_object=empty(rot=(0, 72, 0)))
flower = boolean(prism(8, r=0.06, length=0.04, axis="y", tag="petal"), petals, op="union")
part("flower", flower, at=(0, 0.3, 0.6))

half = extrude(box(0.4, 0.2, 0.2, tag="stone").move(x=0.15), "+x", 0.1)   # crosses x = 0 a little
block = half.modify("MIRROR", use_axis=(True, False, False), use_bisect_axis=(True, False, False), use_clip=True)
part("block", block, at=(0, 0.1, -0.6))
```

- ARRAY counts are cheap to edit: change `count` and rebuild instead of adding pieces.
- A radial ARRAY rotates each copy by the empty's rotation: 360 / count around the axis the copies turn about.
- Parts that move on their own (wheels, doors) are never ARRAY copies: they need their own part and joint.
- **Join or union?** Copies that don't touch (rivets on a plate, slats with gaps) go together with `join` or ARRAY
  without merging: no extra triangles. Copies that must cross their base (spokes into a hub) need
  `boolean(..., op="union")`, which adds faces at every crossing; read the part's `triangles` and `booleans` in the
  report, and lower the copy count first when it is over budget.
- `instance` keeps one mesh in the export (smaller files) and each copy gets its own name for the game.
- Vary repeats in rustic styles: `jitter` the source with a small amount before the ARRAY, or use `instance` with
  slightly different rotations.
