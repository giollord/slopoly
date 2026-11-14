---
title: Cart (hand cart, wagon)
tags: [cart, handcart, wagon, wheelbarrow, barrow, cart bed, vehicle, wooden cart, farm]
summary: How to build a cart - an open bed (hollow container) with plank seams, one axle with mirrored spoked wheels, curved handles or a shaft, legs or a stand - and the order to model it in.
---

**Parts.** bed (root), axle (rotates on X), wheel_L/R (children of the axle), handle_L/R (curved, mirrored), and a
leg or stand pair when the cart rests level. Sacks, hay or crates inside are separate parts overlapping the bed.

**Proportions** (hand cart): bed about 0.9 × 0.3 × 1.2 m (W × H × L), its bottom at about wheel-radius height; wheel
diameter 0.5–0.7 m, the wheels outside the bed's width; handles 0.8–1.0 m long beyond the bed, rising to hip
height (0.8–0.9 m) at the grips.

**Techniques**

- bed: "hollow-containers" (inset + negative extrude), seams from "surface-texture", chips from
  "wear-and-imperfections";
- wheels and axle: "wheeled-objects";
- handles: "curved-parts";
- pivots: "joints-and-moving-parts".

```python
bed = box(0.9, 0.3, 1.2, tag="wood")
bed = extrude(inset(bed, "top", 0.04, tag="wood inside"), "wood inside", -0.24, tag="wood inside")
seam = box(0.92, 0.012, 1.22, tag="wood dark").move(0, -0.05, 0)
bed = boolean(bevel(bed, 0.01, faces="wood"), seam)
part("bed", bed, at=(0, 0.47, 0))

r = 0.3
rim = curve(path([(r, 0, 0), (0, r, 0), (-r, 0, 0), (0, -r, 0)], closed=True), ngon(6, r=0.028), resolution=3,
            tag="wood dark")
spokes = box(0.025, r, 0.025, tag="wood").move(y=r / 2).modify(
    "ARRAY", count=6, use_relative_offset=False, use_object_offset=True, offset_object=empty(rot=(0, 0, 60)))
wheel = join(rim, spokes, prism(8, r=0.06, length=0.1, axis="z", tag="metal")).rotate(y=90)
part("axle", prism(6, r=0.035, length=1.24, axis="x", tag="metal"), parent="bed", at=(0, 0.33, 0.15),
     joint=rotate("x"), overlaps=["bed"])
part("wheel_L", wheel, parent="axle", at=(0.57, 0.33, 0.15), overlaps=["axle"], mirror="x")

handle = curve([(0, 0, 0), (0, 0.04, -0.5), (0, 0.22, -0.95)], ngon(6, r=0.03), resolution=3, tag="wood dark")
part("handle_L", handle, parent="bed", at=(0.36, 0.5, -0.5), overlaps=["bed"], mirror="x")
leg = box(0.05, 0.36, 0.05, tag="wood dark")
part("leg_L", leg, parent="bed", at=(0.36, 0.18, -0.5), overlaps=["bed"], mirror="x")
```

- Score the side view first: wheel size and position, bed length, handle curve. The front view checks the track
  width (wheels outside the bed).
- Two-wheeled carts tip forward onto legs or the handles; four-wheeled wagons have two axles and no legs.
- Keep the triangle count around 500–1000; spokes and the rim are the biggest cost.
