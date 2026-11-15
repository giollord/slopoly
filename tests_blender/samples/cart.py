# Wooden cart: the end-to-end sample (Y up, metres, front faces +Z). Palette roles: wood, wood dark, metal.
bed = bevel(box(0.8, 0.3, 0.7), 0.02)
part("bed", bed, at=(0, 0.49, 0), color="wood")

# Axle under the bed; its origin is on the axis, so the wheels spin with it.
part("axle", prism(6, r=0.04, length=1.1, axis="x"), parent="bed", at=(0, 0.3, 0),
     joint=rotate("x"), color="metal")

# Low-poly wheel: 8 rim faces, a hub on the outer side. The mirror puts the hub outside on the other wheel too.
wheel = extrude(inset(prism(8, r=0.3, length=0.08, axis="x"), "+x", 0.2, tag="metal"), "metal", 0.03)
part("wheel_L", wheel, parent="axle", at=(0.5, 0.3, 0), color="wood dark", overlaps=["axle"], mirror="x")

# Handles start on the bed's back face and bend up at the end.
handle = curve([(0, 0, 0), (0, 0, -0.6), (0, 0.1, -0.85)], ngon(6, r=0.03), smooth=False, resolution=1)
part("handle_L", handle, parent="bed", at=(0.3, 0.55, -0.35), color="wood dark", mirror="x")

socket("hitch", at=(0, 0.55, -1.2), parent="bed")
