---
title: Foliage - trees, bushes, leaves and grass
tags: [tree, trees, pine, fir, conifer, bush, shrub, canopy, crown, leaves, leaf, foliage, grass, plant, plants, flower, cast, displace]
summary: Low-poly plants - canopies as rounded noisy blobs, pines as stacked cones, leaves as thin shells, grass as clustered blades; trunks and branches from the organic-shapes technique.
---

- **Round canopies** (oak, bush): a box with SUBSURF, CAST into a ball, DISPLACE for lumps, DECIMATE back down. Two
  or three blobs of different sizes read better than one.
- **Conifers:** 3–4 `cone`s stacked, each smaller, slightly overlapping, with a little `jitter`.
- **Leaves, palm fronds, big flowers:** thin shells (see "thin-shells-and-panels"), cloned with a radial ARRAY.
- **Grass tufts and reeds:** a thin `cone(3, ...)` blade, bent with a ramp group, cloned radially with a few
  different tilts.
- **Trunks and branches:** see "organic-shapes".

```python
trunk = group(prism(6, r=0.08, length=0.9, tag="bark").move(y=0.45), "top", weight=ramp("y"))
part("trunk", trunk.scale(0.6, 1, 0.6, group="top"))
crown = (box(0.9, 0.8, 0.9, tag="leaves")
         .modify("SUBSURF", levels=1).modify("CAST", factor=0.8)
         .modify("DISPLACE", texture=texture("CLOUDS", noise_scale=0.5), strength=0.12)
         .modify("DECIMATE", ratio=0.6))
part("crown", crown, parent="trunk", at=(0, 1.2, 0), overlaps=["trunk"])

for i, (size, y) in enumerate([(0.7, 0.5), (0.55, 0.85), (0.38, 1.15)]):
    part(f"pine_{i}", jitter(cone(7, r=size, length=0.55, tag="needles"), 0.015, seed=i), at=(1.5, y, 0),
         parent=f"pine_{i - 1}" if i else None, overlaps=[f"pine_{i - 1}"] if i else [])
```

- Two leaf roles (light on top, dark below) add depth in flat shading: `paint` with a face selector on the normal.
- Keep canopies closed solids that overlap the trunk (list it in `overlaps`).
- Budget: 300–1500 triangles per tree; spend them on the silhouette of the crown.
