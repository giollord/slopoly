---
title: Bevels and chamfers
tags: [bevel, bevels, chamfer, chamfered, rounded, edges, corners, soft, highlight, silhouette, bevel modifier]
summary: Where and how much to bevel - one-segment chamfers on silhouette edges catch light in flat shading; the BEVEL modifier with an angle limit for whole shapes; keep them within budget.
---

A one-segment chamfer is the cheapest way to make a box read as made, not placeholder: the extra face catches a
different shade in flat shading.

- `bevel(shape, width, segments=1, faces=..., angle=30)` bevels the edges of selected faces now, only where the faces
  meet at `angle` degrees or more. It refuses (an error) rather than leave a broken mesh.
- The BEVEL modifier bevels the whole shape, and `limit_method="ANGLE"` keeps it to sharp edges only (good after
  booleans or deforms, which add edges that shouldn't be bevelled).

```python
crate = bevel(box(0.6, 0.6, 0.6, tag="wood"), 0.02)
part("crate", crate)
post = prism(6, r=0.06, length=1.0, tag="wood").modify("BEVEL", width=0.012, segments=1, limit_method="ANGLE")
part("post", post, at=(0.6, 0.2, 0))
top = bevel(box(1.0, 0.06, 0.5, tag="stone"), 0.02, faces="top")
part("slab", top, at=(-0.9, 0.0, 0))
```

- Width: 2–4 % of the part's smallest size. Wider looks soft and toy-like (good for cute styles).
- `segments=2–3` only on hero parts seen up close; each segment adds a row of faces on every edge.
- Bevel the edges you see in the silhouette and the top edges that catch light; skip hidden ones (`faces=`).
- Bevel before `jitter` for chipped edges (see "wear-and-imperfections").
- **Bevel last** among the shaping steps: after `inset`, `extrude` and `boolean`. Bevelling first and then cutting
  (seams, holes) leaves slivers and bent faces at the cut corners; insetting a bevelled face is fine.
- A wrap-around seamed box (cart bed, crate) is the exception: leave it unbevelled, or bevel a separate trim part
  (see "wear-and-imperfections").
