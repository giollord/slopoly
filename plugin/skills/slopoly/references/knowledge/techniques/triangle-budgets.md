---
title: Triangle budgets by asset kind
tags: [budget, triangles, polycount, character, prop, building, vehicle, plant, low-poly]
summary: Typical triangle budgets per kind of asset; set an asset's own budget when it differs from the pack default.
---

The pack has a default budget; give an asset its own (`slopoly asset new ... --budget N`) when its kind needs a
different one. Set it when you create the asset, from the parts you expect: add up a share per part (a plank 12, a
wheel 60–150, a lathed part 50–200, a horn 60–100) and compare with the table. Typical low-poly ranges:

| Kind | Triangles |
|---|---|
| Small props (brick, bottle, mushroom, tool) | 50–300 |
| Medium props (crate, barrel, bench, sign) | 200–800 |
| Vehicles and furniture (cart, table, well) | 500–1500 |
| Hero vehicles and machines (locomotive, siege engine, airship) | 3000–6000 |
| Plants (tree, bush) | 300–1500 |
| Buildings (hut, tower) | 800–3000 |
| Characters and creatures | 1500–4000 |

- Spend triangles where the silhouette is: round parts that are seen in profile (wheels, heads) get 8–12 segments,
  hidden or small ones 5–6.
- Wear and grooves (see "wear-and-imperfections" and "surface-texture") cost triangles: budget ~10–20 % for them on rustic assets.
- Modifiers multiply triangles: SUBSURF ×4 per level, SCREW `steps` × profile points, ARRAY `count` × the source,
  curves `resolution` × spans × profile sides. Read `triangles` per part in the report.
- `boolean` costs more than it looks: each union or difference cuts new edges where the shapes cross, often
  doubling the faces near the cut. `join` of shapes that don't touch costs nothing extra. Prefer `join` for pieces
  that only need to be one part, and profile steps (see "lathed-shapes") for bands.
- If the build is over budget, reduce segment counts, resolutions and array counts first, then add DECIMATE
  (`ratio` 0.4–0.7, or `decimate_type="DISSOLVE"` for flat areas), then remove booleans, then merge small parts.
