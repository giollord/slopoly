---
title: Blocking out from primitives
tags: [start, blockout, block, primitives, proportions, parts, plan, approach, modelling, low-poly]
summary: How to start any asset - big masses first from primitives sized from the views, one part per moving or separately coloured piece, then shape with modifiers, then details.
---

Don't model vertex by vertex. Every asset starts as a few primitives that match the views' proportions, then each
primitive is shaped by modifiers and operations.

**Order of work**

1. **Masses.** One primitive per big volume (body, roof, trunk, bed). Size them from the views: the side view gives
   length and height, the front view width. Score the silhouette now: if the masses don't match, details won't help.
2. **Parts.** Split where the object moves (wheels, lids, doors) or changes material. A part is one piece that
   keeps one origin; moving parts are built around their pivot (see "joints-and-moving-parts").
3. **Shape.** Turn each primitive into its real form with the matching technique: curves for bent parts, SCREW for
   round ones, groups plus deforms for organic ones, ARRAY or `instance` for repeats, booleans or inset/extrude for
   openings.
4. **Details.** Bevels where the silhouette catches light, wear for rustic styles, surface texture last, and only
   when the triangle budget allows.

```python
top = bevel(box(1.2, 0.08, 0.6, tag="wood"), 0.015)
part("top", top, at=(0, 0.72, 0))
leg = box(0.07, 0.68, 0.07, tag="wood dark")
part("leg_front_L", leg, parent="top", at=(0.52, 0.34, 0.22), mirror="x")
part("leg_back_L", leg, parent="top", at=(0.52, 0.34, -0.22), mirror="x")
apron = box(0.96, 0.08, 0.02, tag="wood dark")
instance("apron", apron, [(0, 0.64, 0.25), (0, 0.64, -0.25)], parent="top")
```

- Pick the primitive by cross-section: square things from `box`, round ones from `prism` (6–12 sides) or an
  `outline` turned with SCREW, tapering ones from `cone`.
- Shapes are centred on their origin: place a part's origin where it attaches or pivots.
- Symmetric pairs: build one with `_L` and `mirror="x"`; repeated identical pieces: `instance` or ARRAY.
- Use as few parts as the object needs: a part per plank is rarely worth it; a groove or seam reads the same.
