---
title: Steam locomotive (engine, loco)
tags: [locomotive, loco, steam engine, train, engine, boiler, smokebox, smokestack, chimney, funnel, cab, cowcatcher, pilot, plough, driving wheels, tender, vehicle, machine, rail]
summary: How to build a steam locomotive - a frame with a lathed boiler and smokebox, a banded smokestack, a dome, a cab with a curved roof, driving wheels and a V-shaped cowcatcher - with real sizes, a 3,000-6,000 triangle budget and the order to model it in.
---

**Size and budget.** A small locomotive is 6–9 m long, 2.5–3 m wide and 3.5–4.5 m tall to the chimney top. State
the length when creating the asset (`--size z=8`). With 20–40 parts it is a hero vehicle: budget 3,000–6,000
triangles from the start.

**Parts** (front at +Z). Segment with coarse names first (`boiler, cab, chimney, wheels, cowcatcher`), then refine.

- frame (root): a long low box, the running board on top.
- boiler: lathed (`outline` + SCREW), lying along Z, with bands as profile steps (see "lathed-shapes"); smokebox at
  the front, a little wider and darker, its door on the front face.
- smokestack: lathed, flared, with a banded rim (see "lathed-shapes"); a dome and a sand box as small lathed humps
  on the boiler's top.
- cab: at the back, a box with window cut-outs (see "holes-and-openings") and a curved roof sheet overhanging it
  (see "curved-parts").
- wheels: driving wheels as mirrored parts with rotate joints (see "wheeled-objects"), smaller leading wheels;
  coupling rods as thin boxes along the wheel centres.
- cowcatcher (pilot): a **V in plan**, its point forward at the bottom, sloping back up to the buffer beam. Two
  slanted arms crossing at the point, not a flat bar: check it from `slopoly look --from top`.
- pipes and rails: `curve`s along the boiler (see "curved-parts").

**Order.** Frame, boiler and cab first (they set the silhouette), then wheels, then smokestack and dome, then the
cowcatcher, then pipes, rails and rivets.

```python
part("frame", box(1.6, 0.25, 6.4, tag="iron dark"), at=(0, 0.95, 0))

profile = [(0, 0), (0.62, 0), (0.62, 1.2), (0.645, 1.2), (0.645, 1.3), (0.62, 1.3), (0.62, 2.5), (0.645, 2.5),
           (0.645, 2.6), (0.62, 2.6), (0.62, 3.6), (0, 3.6)]
boiler = outline(profile, tag="iron").modify("SCREW", axis="Y", steps=10, use_merge_vertices=True)
boiler = paint(boiler, "brass", faces=lambda c, n: 1.15 < c[1] < 1.35 or 2.45 < c[1] < 2.65)
part("boiler", boiler.move(y=-1.8).rotate(x=90), parent="frame", at=(0, 1.72, 0.9), overlaps=["frame"])

stack = outline([(0, 0), (0.26, 0), (0.18, 0.12), (0.16, 0.6), (0.3, 0.95), (0.34, 0.95), (0.34, 1.02), (0, 1.02)],
                tag="iron dark").modify("SCREW", axis="Y", steps=8, use_merge_vertices=True)
part("smokestack", paint(stack, "brass", faces=lambda c, n: c[1] > 0.94), parent="boiler", at=(0, 2.22, 2.3),
     overlaps=["boiler"])

cab = box(1.7, 1.5, 1.5, tag="wood")
cab = boolean(cab, box(2.0, 0.5, 0.6, tag="wood dark").move(y=0.25))
part("cab", cab, parent="frame", at=(0, 1.83, -2.3), overlaps=["frame", "boiler"])
roof = curve(path([(-1.0, 0, 0), (0, 0.25, 0), (1.0, 0, 0)]),
             [(-0.03, -0.9), (0.03, -0.9), (0.03, 0.9), (-0.03, 0.9)], resolution=4, tag="iron dark")
part("cab_roof", roof, parent="cab", at=(0, 2.6, -2.3), overlaps=["cab"])

wheel = prism(10, r=0.6, length=0.12, axis="x", tag="iron dark")
part("wheel_L1", wheel, parent="frame", at=(0.72, 0.6, -1.2), joint=rotate("x"), overlaps=["frame"], mirror="x")
part("wheel_L2", wheel, parent="frame", at=(0.72, 0.6, 0.2), joint=rotate("x"), overlaps=["frame"], mirror="x")

arm = box(0.06, 0.45, 1.05, tag="iron dark")
plough = boolean(arm.rotate(y=-49).move(x=0.33), arm.rotate(y=49).move(x=-0.33), op="union")
part("cowcatcher", plough, parent="frame", at=(0, 0.45, 3.45), overlaps=["frame"])
```

- Score the side view first (boiler length and height, wheel size and spacing, chimney height), then the top view
  for the cowcatcher's V and the cab's width.
- The reference mesh's smoke and steam are not parts: the hero prompt asks for none, and a leftover plume is
  explained, not modelled.
- Repeated details (rivets, boiler bands, spokes) are the triangle sinks: bands as profile steps, rivets only where
  the silhouette shows them.
