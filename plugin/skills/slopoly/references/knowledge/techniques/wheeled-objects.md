---
title: Wheeled objects
tags: [wheel, wheels, spoked, spokes, spoke, rim, hub, axle, cart, wagon, carriage, wheelbarrow, vehicle, radial, array]
summary: Wheels as one part each - a ring rim from a closed curve, spokes cloned with a radial ARRAY, a hub prism - on a rotating axle, mirrored to the other side.
---

A wheel is one part (it turns as one), built in the XY plane around its axle (Z), then turned to face X.

- **Rim:** a closed `curve` through 4 points around the centre (`resolution=3` gives 12 segments).
- **Spokes:** one spoke from the hub to the rim, cloned around the axle with a radial ARRAY: object offset with an
  `empty` rotated by 360°/count. All spokes stay in one mesh with the spoke's tag.
- **Hub:** a short `prism` along the axle, a little thicker than the spokes.
- **Axle:** a part with `joint=rotate("x")`, its origin on the axle line; wheels are its children with `overlaps`
  to it, built with `mirror="x"`.

```python
r = 0.3
rim = curve(path([(r, 0, 0), (0, r, 0), (-r, 0, 0), (0, -r, 0)], closed=True), ngon(6, r=0.03), resolution=3,
            tag="wood dark")
spoke = box(0.025, r, 0.025, tag="wood").move(y=r / 2)
spokes = spoke.modify("ARRAY", count=6, use_relative_offset=False, use_object_offset=True,
                      offset_object=empty(rot=(0, 0, 60)))
hub = prism(8, r=0.06, length=0.1, axis="z", tag="metal")
wheel = boolean(boolean(rim, spokes, op="union"), hub, op="union").rotate(y=90)   # union: a joined overlap fails

part("bed", box(0.9, 0.25, 1.2, tag="wood"), at=(0, 0.45, 0))
part("axle", prism(6, r=0.035, length=1.2, axis="x", tag="metal"), parent="bed", at=(0, 0.3, 0),
     joint=rotate("x"), overlaps=["bed"])
part("wheel_L", wheel, parent="axle", at=(0.55, 0.3, 0), joint=rotate("x"), overlaps=["axle"], mirror="x")
```

- **Solid or disc wheels** (toy carts, carts in the distance): `prism(8–12, ...)` with `inset` + `extrude` on the
  side face for the hub, no spokes.
- 6–8 spokes read as spoked at game distance; 12+ only for hero props. The rim needs 10–16 segments to look round
  in the side view.
- Spoke thickness ~8–10 % of the radius, rim tube ~10 %.
- Wheels never touch the bed: the axle connects them. Put the bottom of the wheel at y = 0 (the ground).
- Four wheels: two axles (front, back), each with a mirrored wheel pair.

## Many wheels on a budget: spokes extruded from the hub, the rim apart

Unioning a rim, an ARRAY of spokes and a hub costs far more than its pieces: the boolean re-triangulates every face
where they meet, and fewer spokes can even cost more. On a locomotive, a unioned wheel came to 356–456 triangles.
Without booleans the same wheel costs a third to a half of that:

- **Hub and spokes in one mesh:** a hub prism whose side faces are pulled out into spokes with
  `bmesh.ops.extrude_discrete_faces`, each new end face narrowed and moved out to the rim (about 70 triangles for 6
  spokes).
- **Rim as its own part:** the ring rim, a child of the wheel that overlaps the spoke ends (segments × tube sides × 2
  triangles: 96 for 8 segments of a 6-sided tube, 144 for the 12 below).
- **The hub part is the wheel:** it sits on the axle and turns with it. A ring rim alone never touches the axle, so
  it can't be the part that the axle holds.

```python
r, hub_r = 0.3, 0.05
hub = prism(6, r=hub_r, length=0.06, axis="z", tag="wood")
bm = hub.bm
sides = [f for f in bm.faces if abs(f.normal.z) < 0.5]
for face in bmesh.ops.extrude_discrete_faces(bm, faces=sides)["faces"]:
    out, centre = face.normal.copy(), face.calc_center_median()
    for v in face.verts:  # a narrower spoke end, just inside the rim tube
        v.co = centre + (v.co - centre) * 0.5 + out * (r - 0.02 - centre.length)
rim = curve(path([(r, 0, 0), (0, r, 0), (-r, 0, 0), (0, -r, 0)], closed=True), ngon(6, r=0.03), resolution=3,
            tag="wood dark")

part("bed", box(0.9, 0.25, 1.2, tag="wood"), at=(0, 0.45, 0))
part("axle", prism(6, r=0.035, length=1.2, axis="x", tag="metal"), parent="bed", at=(0, 0.3, 0),
     joint=rotate("x"), overlaps=["bed"])
part("wheel_L", hub.rotate(y=90), parent="axle", at=(0.55, 0.3, 0), joint=rotate("x"), overlaps=["axle"],
     mirror="x")
part("rim_L", rim.rotate(y=90), parent="wheel_L", at=(0.55, 0.3, 0), overlaps=["wheel_L"], mirror="x")
```
