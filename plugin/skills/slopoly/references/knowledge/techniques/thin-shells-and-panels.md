---
title: Thin shells and panels
tags: [thin, shell, panel, panels, sheet, cloth, awning, canopy, banner, flag, leaf, leaves, roof, bowl, cup, solidify, thickness, ribbon]
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
