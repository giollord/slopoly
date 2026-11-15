---
title: Wear, chips, cracks and dents
tags: [seam, seams, plank, ring, crate, wear, worn, old, chips, chipped, cracks, cracked, dents, damage, imperfections, weathered, wood, stone, jitter, rustic]
summary: Make rustic or old objects look used - jitter for uneven shapes (safely on thin walls), bevel+jitter for chipped edges, thin darker grooves for cracks and plank seams.
---

Perfect boxes look like placeholders. For rustic, old or hand-made styles add a little irregularity, within budget.

**Uneven shapes and dents** — `jitter` the whole part by 1–3 % of its size, with a different `seed` per part so
mirrored or repeated parts don't look stamped:

```python
plank = jitter(bevel(box(1.0, 0.06, 0.2), 0.01), 0.008, seed=4)
part("plank", plank, color="wood")
```

**Chipped edges** — bevel, then jitter by about the bevel width, so the bevelled corners become uneven:

```python
post = jitter(bevel(box(0.12, 1.0, 0.12), 0.015), 0.01, seed=7)
part("post", post, color="wood")
```

**Cracks and plank seams** — subtract a thin box tagged with a darker role; the cut faces take the cutter's tag, so
the groove shows as a dark line. Add the darker role to the palette ("wood crack", ~30 % darker than "wood").

```python
side = box(0.8, 0.3, 0.04, tag="wood")
seam = box(0.82, 0.012, 0.02, tag="wood crack").move(0, 0.05, 0.02)   # shallow: 1/2 of the thickness at most
crack = box(0.25, 0.01, 0.02, tag="wood crack").rotate(0, 0, 12).move(-0.2, -0.06, 0.02)
side = boolean(boolean(side, seam), crack)
part("side", side)
```

**Seams around an open box** (a cart bed, a crate): cut each seam with one closed ring, an outer box minus an inner
box, joined for all heights and subtracted once. Four overlapping wall cutters leave non-manifold edges at the
corners, and seams cut through bevelled corners leave slivers and bent faces, so leave the seamed box unbevelled (or
bevel a separate trim part). The groove depth is half of the outer width minus the inner width; keep the rings off
the cavity floor and the rim.

```python
W, H, L = 0.9, 0.5, 1.2
bed = extrude(inset(box(W, H, L, tag="wood"), "top", 0.05, tag="wood inside"), "wood inside", -(H - 0.07),
              tag="wood inside")
ring = boolean(box(W + 0.04, 0.014, L + 0.04, tag="wood crack"), box(W - 0.02, 0.03, L - 0.02, tag="wood crack"))
bed = boolean(bed, join(*[ring.move(0, y, 0) for y in (-0.12, 0.0, 0.12)]))
part("bed", bed, at=(0, 0.6, 0))
```

- 1–3 grooves per large face are enough; each boolean costs triangles and is counted in the report.
- Cracks go across the grain (a slight angle), seams along plank borders.
- Stone: jitter more (3–5 %), add 1–2 short cracks; metal: dents only (jitter on one face), no cracks.
- Keep wear off small parts (< 10 cm): it only adds noise.
- Many grooves (planks, bark): clone one cutter with an ARRAY and subtract once (see "surface-texture").
- Lumpy, weathered stone or old plaster: a light DISPLACE with `texture("CLOUDS")` after SUBSURF `levels=1`, then
  DECIMATE (see "rocks-and-chunks"); `jitter` stays the cheapest for boxes.
- Check the triangle total after adding wear; drop seams before cracks when over budget.

**Jitter on thin walls.** A jitter larger than half a wall's thickness pushes vertices through the other side, and
the part fails as self-intersecting. `jitter` limits each move to under half the wall behind the vertex and adds a
warning to the part's `warnings` when the shape still cuts through itself. On thin parts (panels, shutters, cab
walls, sheets):

- keep the amount under a third of the thickness (a 2 cm board: at most 6 mm);
- jitter one side for dents (`faces="front"`), not the whole part;
- jitter after booleans that cut windows: the pillars between windows are the thinnest walls.

```python
shutter = boolean(box(0.6, 0.8, 0.02, tag="wood"), box(0.2, 0.25, 0.1, tag="wood dark").move(y=0.15))
part("shutter", jitter(shutter, 0.006, seed=3, faces="front"))
```
