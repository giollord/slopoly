---
title: Rocks, chunks and lumps
tags: [rock, rocks, stone, stones, boulder, pebble, chunk, cliff, ore, crystal, lumpy, irregular, displace, cast, decimate, noise]
summary: Irregular natural solids - a subdivided primitive pushed by DISPLACE with a noise texture, rounded or flattened with CAST, and cut back to low-poly with DECIMATE; vary each one through the texture's position.
---

Rocks are a primitive with a little more geometry, pushed by noise, then reduced again:

1. SUBSURF `levels=1` (or 2 for big rocks) on a `box` or `prism`.
2. DISPLACE with `texture("CLOUDS", noise_scale=...)` and a `strength` of 10–25 % of the size.
3. DECIMATE `ratio` 0.3–0.6 for the faceted low-poly look and the budget.

Move the noise per rock with `texture_coords="OBJECT"` and `texture_coords_object=empty(at=...)`: each position
gives a different rock from the same program.

```python
def rock(seed, size=0.4):
    return (box(size, size * 0.7, size * 0.9, tag="stone")
            .modify("SUBSURF", levels=1)
            .modify("DISPLACE", texture=texture("CLOUDS", noise_scale=0.35), strength=size * 0.4,
                    texture_coords="OBJECT", texture_coords_object=empty(at=(seed * 1.7, seed * 0.9, 0)))
            .modify("DECIMATE", ratio=0.5))

part("boulder", rock(1, 0.6))
part("stone_1", rock(2, 0.25), at=(0.6, 0, 0.2))
part("stone_2", rock(3, 0.18), at=(-0.5, 0, 0.3))
```

- CAST `factor` 0.3–0.8 before DISPLACE rounds a box into a pebble; a negative factor flattens.
- Crystals and ore: `cone(5–6, ...)` with `jitter`, a few in a cluster with different rotations, no noise.
- Cliffs: a large box with SUBSURF 2, DISPLACE with a larger `noise_scale`, then `bevel` the top face.
- Put the rock's base flat on the ground: cut the bottom with a boolean box or scale the bottom group flat.
