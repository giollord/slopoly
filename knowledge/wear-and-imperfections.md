---
title: Wear, chips, cracks and dents
tags: [wear, worn, old, chips, chipped, cracks, cracked, dents, damage, imperfections, weathered, wood, stone, jitter, rustic]
summary: Make rustic or old objects look used - jitter for uneven shapes, bevel+jitter for chipped edges, thin darker grooves for cracks and plank seams.
---

Perfect boxes look like placeholders. For rustic, old or hand-made styles add a little irregularity, within budget.

**Uneven shapes and dents** — `jitter` the whole part by 1–3 % of its size, with a different `seed` per part so
mirrored or repeated parts don't look stamped:

```python
plank = jitter(bevel(box(1.0, 0.06, 0.2), 0.01), 0.008, seed=4)
```

**Chipped edges** — bevel, then jitter by about the bevel width, so the bevelled corners become uneven:

```python
post = jitter(bevel(box(0.12, 1.0, 0.12), 0.015), 0.01, seed=7)
```

**Cracks and plank seams** — subtract a thin box tagged with a darker role; the cut faces take the cutter's tag, so
the groove shows as a dark line. Add the darker role to the palette ("wood crack", ~30 % darker than "wood").

```python
side = box(0.8, 0.3, 0.04, tag="wood")
seam = box(0.82, 0.012, 0.02, tag="wood crack").move(0, 0.05, 0.02)   # shallow: 1/2 of the thickness at most
crack = box(0.25, 0.01, 0.02, tag="wood crack").rotate(0, 0, 12).move(-0.2, -0.06, 0.02)
side = boolean(boolean(side, seam), crack)
```

- 1–3 grooves per large face are enough; each boolean costs triangles and is counted in the report.
- Cracks go across the grain (a slight angle), seams along plank borders.
- Stone: jitter more (3–5 %), add 1–2 short cracks; metal: dents only (jitter on one face), no cracks.
- Keep wear off small parts (< 10 cm): it only adds noise.
- Check the triangle total after adding wear; drop seams before cracks when over budget.
