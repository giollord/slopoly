---
title: Thin shells and panels
tags: [thin, shell, panel, panels, sheet, cloth, awning, canopy, banner, flag, leaf, leaves, roof, bowl, cup, solidify, thickness, ribbon, torn, ragged, tattered, curtain, bisect]
summary: Thin things (cloth, awnings, banners, leaves, bowls, roof sheets) as a surface given thickness with SOLIDIFY - from a lathed open profile or a ribbon swept from a line with SCREW.
---

A surface plus SOLIDIFY is the cleanest thin part: one setting controls the thickness and the result is closed.

- **Open round shells** (bowls, cups, lampshades, domes): an `outline` profile that starts on the axis and ends at
  the rim, turned with SCREW, then SOLIDIFY.
- **Strips and sheets** (awnings, banners, cloth draped over a cart, leaves): a line swept sideways with SCREW
  (`angle=0`, `screw_offset` = width, `steps` = rows across), shaped by its points, then SOLIDIFY.

```python
bowl = outline([(0, 0), (0.12, 0.02), (0.2, 0.08), (0.24, 0.16)], tag="clay")
bowl = bowl.modify("SCREW", axis="Y", steps=8, use_merge_vertices=True).modify("SOLIDIFY", thickness=0.015)
part("bowl", bowl)

# the profile across the awning (from the wall out, sagging a little), swept 1.2 m along X in 4 rows
awning = outline([(0, 0.6, 0), (0, 0.52, 0.25), (0, 0.42, 0.5)], tag="cloth")
awning = awning.modify("SCREW", axis="X", angle=0, screw_offset=1.2, steps=4)
part("awning", awning.modify("SOLIDIFY", thickness=0.02), at=(-0.6, 0.5, 0.8))
```

- Thickness: 1–3 cm for cloth and leaves at prop scale; thinner disappears and flickers in game.
- `offset` picks the side the thickness grows to (-1 inside, 0 centred, 1 outside).
- SOLIDIFY on a closed mesh makes a hollow shell with an inner surface: useful for a hollow log with the ends cut by
  a boolean.
- Sag a sheet with a group and `move(y=..., group=)` weighted by a function of distance from its edges.

## Torn cloth and ragged edges, without booleans

Ragged hems made by unioning cones or wedges into a sheet cost hundreds of triangles, and the count jumps whenever the
sheet's size changes, because the boolean re-triangulates the merged faces. Cut the sheet into strips instead and
pull the bottom of each cut down into a tongue: a few triangles per tongue, and the count doesn't depend on the size.

```python
w, h, strips = 0.8, 1.0, 5
banner = box(w, h, 0.03, tag="cloth")
bm = banner.bm
for i in range(1, strips):  # vertical cuts across the whole sheet, front and back
    bmesh.ops.bisect_plane(bm, geom=list(bm.verts) + list(bm.edges) + list(bm.faces),
                           plane_co=(-w / 2 + w * i / strips, 0, 0), plane_no=(1, 0, 0))
tongues = (0.05, 0.18, 0.08, 0.22, 0.04, 0.15)  # one per cut line, edges included: vary them
for v in bm.verts:
    if v.co.y < -h / 2 + 1e-4:  # the bottom edge: front and back move together, so the sheet stays closed
        v.co.y -= tongues[round((v.co.x + w / 2) / (w / strips))]
part("banner", banner, at=(0, 1.5, 0))
```

- Vary the tongue lengths irregularly; equal teeth read as a pattern, not as wear.
- For holes, cut a few more lines and pull single vertices up as well as down.
- Avoid `jitter` on thin cloth made with booleans: it can push the faces through each other. Shape the variation
  with the cuts instead.
