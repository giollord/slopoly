---
title: Bone decorations (ribs, skulls, tusks on orcish and tribal objects)
tags: [bone, bones, rib, ribs, ribcage, spine, vertebra, skull, tusk, tusks, horn, trophy, orcish, orc, tribal, barbarian, decoration, totem]
summary: How to build bone decorations - ribs bent from a curve with knobbed ends, a spine of repeated vertebrae, tusks and horns from one tapered helper - and how to check which way they bend and where their ends are.
---

Bones on orcish or tribal objects are decoration: a few strong shapes read better than many thin ones. Their
character is in **which way they curve and where the knobbed ends are**, so read both from a close-up
(`slopoly look --region ribs --from 60,20`) and write them in the shape plan before building. The common mistake is a
rib curving the wrong way, or its knob at the bottom instead of beside the spine.

**Parts.**

- ribs: a `curve` through 3 points (out, then down), round profile of 5 sides, a knob at the spine end; mirrored
  with `mirror="x"`, repeated along the spine with ARRAY (they don't touch, so no boolean).
- spine: one vertebra (a short prism with a fin), repeated with ARRAY.
- tusks and horns: the `horn_shape` helper from "organic-shapes".
- skulls: a bevelled box or a lathed dome, eye holes cut with `boolean`, a jaw as a separate box.
- Use one bone role ("bone", ivory) and one darker role for knobs and cracks.

```python
def rib(length, r, knob):
    bow = curve([(0, 0, 0), (length * 0.6, -length * 0.15, 0), (length * 0.75, -length, 0)], ngon(5, r=r),
                resolution=3, tag="bone")
    return boolean(bow, prism(6, r=knob, length=knob * 2, axis="z", tag="bone dark"), op="union")


spine = prism(6, r=0.05, length=0.08, axis="z", tag="bone").modify(
    "ARRAY", count=5, use_relative_offset=False, use_constant_offset=True, constant_offset_displace=(0, 0, 0.13))
part("spine", spine, at=(0, 0.6, -0.26))

ribs = rib(0.45, 0.022, 0.04).modify(
    "ARRAY", count=4, use_relative_offset=False, use_constant_offset=True, constant_offset_displace=(0, 0, 0.13))
part("rib_L", ribs, parent="spine", at=(0.04, 0.6, -0.2), overlaps=["spine"], mirror="x")
```

- Knobs at the spine end, the curve going out first and then down: the ribs hang from the spine like a ribcage.
- Space ARRAY copies further apart than the bone's thickness, so they don't touch.
- 4–6 ribs a side are enough; each rib costs 50–80 triangles.
