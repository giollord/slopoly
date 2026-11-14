---
title: Surface texture from meshes
tags: [texture, surface, bark, grooves, groove, planks, plank, stones, bricks, shingles, carving, relief, shrinkwrap, project, solidify, boolean]
summary: Texture made of geometry - wavy strips projected onto a surface with SHRINKWRAP, thickened with SOLIDIFY, then cut in (grooves, bark) or added on (raised planks, stones) with a boolean.
---

Flat-coloured low-poly assets get their texture from a few cuts and bumps, not from images. The pattern:

1. **Strip:** a wavy line (`outline`) swept sideways into a ribbon with SCREW (`angle=0`, `screw_offset` = strip
   width, `steps=1`): the ribbon trick.
2. **Project:** SHRINKWRAP the ribbon onto the target surface, so it follows the surface wherever it bends.
3. **Thicken:** SOLIDIFY it, centred on the surface (`offset=0`), so half of it is inside.
4. **Repeat:** ARRAY it (linear, or radial around a trunk).
5. **Cut or add:** a BOOLEAN difference makes grooves; a union makes raised strips. Tag the strips with a darker
   (grooves) or lighter (raised) role: cut faces take the strip's tag.

```python
trunk = jitter(prism(8, r=0.15, length=1.0, tag="bark"), 0.01, seed=2)
line = outline([(0.15, -0.45, 0.0), (0.15, -0.15, 0.025), (0.15, 0.15, -0.02), (0.15, 0.45, 0.01)],
               tag="bark dark")
strips = (line.modify("SCREW", axis="Z", angle=0, screw_offset=0.025, steps=1)
          .modify("SHRINKWRAP", target=trunk)
          .modify("SOLIDIFY", thickness=0.02, offset=0)
          .modify("ARRAY", count=5, use_relative_offset=False, use_object_offset=True,
                  offset_object=empty(rot=(0, 72, 0))))
part("trunk", trunk.modify("BOOLEAN", object=strips, operation="DIFFERENCE", solver="MANIFOLD"))
```

**Planks and boards** on a flat wall: a thin box per seam, ARRAY along the wall, subtracted:

```python
wall = box(1.2, 0.8, 0.08, tag="wood")
seam = box(1.22, 0.012, 0.02, tag="wood crack").move(0, -0.3, 0.04)
seams = seam.modify("ARRAY", count=4, relative_offset_displace=(0, 15, 0))
part("wall", boolean(wall, seams))
```

- Depth: 1–3 % of the part's size; deeper looks carved, shallower vanishes at game distance.
- 3–6 strips per surface. Each boolean adds triangles: check the count.
- Stones and bricks: jittered small boxes in an ARRAY, joined with a union, or a surface of `instance`d stones.
- Shingles: overlapping thin boxes in an ARRAY with a slight tilt (`rotate`), no boolean needed.
- SHRINKWRAP needs a target with faces facing the strip; on a box, keep strips inside one face.
