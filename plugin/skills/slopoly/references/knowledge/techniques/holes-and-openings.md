---
title: Holes and openings
tags: [hole, holes, opening, window, windows, door, doorway, cutout, cut, pocket, recess, slot, boolean, inset, extrude, through]
summary: Through-holes with a boolean difference (windows, handle holes), recesses and pockets with inset plus negative extrude (no boolean), and how to keep both clean.
---

Two ways, depending on whether the hole goes through:

- **Through-holes** (a window, a hole in a plank, a ring's opening): BOOLEAN difference with a cutter that is
  longer than the part is thick, so no faces are coplanar. Tag the cutter with a darker role: its faces become the
  hole's walls.
- **Recesses** (a doorway set into a wall, a pocket, a panel, a socket): `inset` the face, then `extrude` it inwards.
  No boolean, fewer triangles, clean quads.

```python
wall = box(1.6, 1.2, 0.12, tag="wall")
window = box(0.35, 0.4, 0.3, tag="window dark").move(-0.4, 0.15, 0)
wall = boolean(wall, window)
door = extrude(inset(box(0.6, 1.0, 0.12, tag="wall"), "front", 0.08, tag="door"), "door", -0.04)
part("wall", wall)
part("door_frame", door, parent="wall", at=(0.45, -0.1, 0.07), overlaps=["wall"])
```

- Round holes: a `prism` cutter with 6–8 sides.
- Several holes: join the cutters into one shape (`join`) and subtract once.
- A cutter that only grazes a face leaves slivers: move it fully through or fully clear.
- Containers (cart beds, crates): see "hollow-containers" for the open-top cavity.
- A hole you only see from one side can be a recess: cheaper and reads the same.
