---
title: Ropes, chains and cables
tags: [rope, ropes, chain, chains, cable, cables, wire, string, cord, coil, coiled, link, links, hanging, sag, catenary]
summary: Ropes and cables as curves with a small profile through sagging control points; coils as closed rings in an ARRAY; chains as one link cloned with an ARRAY that offsets and turns each copy.
---

- **Hanging rope or cable:** a `curve` through 3–5 points that sag in the middle (the lowest point about 10–20 %
  of the span below the ends), profile `ngon(4–5, r)`.
- **Coiled rope:** a closed ring `curve`, repeated with an ARRAY upwards (`relative_offset_displace=(0, 1, 0)`).
- **Chain:** one link (a closed curve, longer than wide), cloned with an ARRAY whose object offset moves by a link
  length and turns by 90°.

```python
rope = curve([(-0.6, 1.0, 0), (-0.2, 0.82, 0), (0.2, 0.82, 0), (0.6, 1.0, 0)], ngon(4, r=0.015), resolution=3,
             tag="rope")
part("rope", rope)

ring = curve(path([(0.15, 0, 0), (0, 0, 0.15), (-0.15, 0, 0), (0, 0, -0.15)], closed=True), ngon(4, r=0.02),
             resolution=2, tag="rope")
part("coil", ring.modify("ARRAY", count=4, relative_offset_displace=(0, 1.05, 0)), at=(1.2, 0.02, 0))  # a hair apart: overlapping or touching rings fail

link = curve(path([(0.05, 0, 0), (0, 0.04, 0), (-0.05, 0, 0), (0, -0.04, 0)], closed=True), ngon(4, r=0.01),
             resolution=2, tag="metal")
chain = link.modify("ARRAY", count=6, use_relative_offset=False, use_object_offset=True,
                    offset_object=empty(at=(0.075, 0, 0), rot=(90, 0, 0)))
part("chain", chain, at=(-1.2, 0.5, 0))
```

- Profiles of 4 sides are enough for thin ropes; a twisted look comes from SIMPLE_DEFORM `TWIST` on a 4-sided rope.
- Ropes tied to parts: start and end the curve inside the parts and list them in `overlaps`.
- Long chains are expensive (each link ~32 triangles at these settings): use 4–8 links or a rope instead.
