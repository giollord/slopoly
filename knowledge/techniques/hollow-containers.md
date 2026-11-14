---
title: Hollow containers
tags: [container, cart, bed, crate, box, barrel, trough, bucket, basket, hole, open, inset, extrude]
summary: Open-topped objects (cart beds, crates, troughs, buckets) need a real cavity, made with inset + negative extrude on the top face.
---

Anything meant to hold things — a cart bed, crate, trough, wheelbarrow, bucket, barrel without a lid — must be
**open**: a solid block reads as a lid or a brick. Make the cavity from the top face instead of building walls
separately; it stays one closed mesh with quads and costs only ~10 extra triangles.

```python
bed = box(0.8, 0.3, 0.7, tag="wood")
bed = inset(bed, "top", 0.04, tag="wood inside")      # rim = wall thickness (3-6 % of the width)
bed = extrude(bed, "wood inside", -0.24, tag="wood inside")  # depth: leave a floor of ~0.05
part("bed", bevel(bed, 0.01, faces="wood"), at=(0, 0.49, 0), color="wood")
```

- Use a separate, slightly darker role for the inside ("wood inside", or reuse a "shadow" role): it reads as depth
  in a flat-shaded palette.
- Round containers: the same on `prism(n, ...)` with `"top"`; for a barrel, inset the top a second time for the rim.
  Lathed containers (buckets, pots, bowls): an `outline` ending at the rim, turned with SCREW and thickened with
  SOLIDIFY (see "lathed-shapes" and "thin-shells-and-panels").
- Thin-walled containers (baskets, troughs with thin boards): SOLIDIFY on the open shape gives even walls with one
  setting; inset + extrude stays cheaper for thick walls.
- Keep the floor thickness above 0 — extruding through the bottom face breaks the mesh.
- If the hero shows cargo (sacks, hay), add it as separate parts inside the cavity with `overlaps` to the bed.
