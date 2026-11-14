---
title: Lathed (round) shapes
tags: [lathe, lathed, screw, spin, revolve, round, vase, pot, bottle, jar, barrel, bucket, column, pillar, mushroom, bowl, cup, lamp, turned]
summary: Round objects with a profile - an outline of (radius, height) points turned around Y with SCREW - for vases, bottles, barrels, columns and mushrooms.
---

Anything turned on a lathe is one profile line spun around its axis. Draw half of its side silhouette as
`outline` points (x = radius, y = height), from the axis at the bottom to the axis at the top, then SCREW it around
Y. `steps` is the number of sides.

```python
vase = outline([(0, 0), (0.12, 0), (0.18, 0.12), (0.14, 0.3), (0.07, 0.38), (0.09, 0.45), (0, 0.45)], tag="clay")
part("vase", vase.modify("SCREW", axis="Y", steps=8, use_merge_vertices=True))

barrel = outline([(0, 0), (0.22, 0), (0.27, 0.3), (0.22, 0.6), (0, 0.6)], tag="wood")
part("barrel", barrel.modify("SCREW", axis="Y", steps=10, use_merge_vertices=True), at=(0.8, 0, 0))
```

- Start and end the profile on the axis (x = 0) and set `use_merge_vertices=True`, so the shape is closed.
- 6–10 steps for props; read the profile from the front view's silhouette, half of its width.
- Open objects (bowls, cups, buckets): end the profile at the rim instead of the axis and thicken with SOLIDIFY
  (see "thin-shells-and-panels"), or use `inset` + `extrude` on a `prism` top (see "hollow-containers").
- Bands and rims (barrel hoops): a closed `curve` ring at that height, or a separate thin `prism`.
- Tags: the whole lathed shape gets the outline's tag; `paint` bands afterwards with a face selector function
  on the height.
