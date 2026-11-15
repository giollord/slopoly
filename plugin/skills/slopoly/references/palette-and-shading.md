# Palette and shading

## Palette

Every asset of a pack is coloured through one palette texture. Each role (a solid colour or a two-colour gradient)
has a fixed slot in it, and faces are tagged with roles in the part program (`color=`, `tag=`, `paint`).

- `slopoly palette show <pack>` lists the roles, their slots and which variants' builds use each role.
- `slopoly palette add <pack> "<role>" "#rrggbb" [--to "#rrggbb"]` adds a solid role, or a gradient with `--to`, in
  the next free slot.
- `slopoly palette set <pack> "<role>" "#rrggbb" [--to ...] [--variant <name>]` recolours a role. The current builds'
  models are refreshed without rebuilding.
- `slopoly palette rm <pack> "<role>"` deletes a role that no build uses (it is refused otherwise).
- `slopoly palette variant <pack> <name>` creates a palette variant (`--rm` deletes it). Set its colours with
  `palette set --variant`. Roles it doesn't set keep the main colours.
- `slopoly palette render <pack>` re-renders the textures and refreshes the current builds' models after a hand edit
  of `palette.yaml`.

Rules:

- **Name roles by usage:** "wall base", "wall accent", "roof", "cart wood", "leaf 1". Use a colour name ("leaf green")
  only for a colour meant to stay the same in every palette.
- **Never move slots.** The CLI assigns them; `slopoly check` reports moved or shared slots.
- **Palette variants affect only previews and exports.** Generation, colour measurement, scoring and modelling use
  the main palette. Make variants only when the user asks.

## Shading

`pack.yaml` sets the shading of every build of the pack:

```yaml
shading:
  mode: flat            # flat: every edge hard; smooth: shared normals, edges sharper than the angle stay hard
  hard_edge_angle: 60   # degrees (0-180); 60 keeps 6-12-sided parts smooth and box corners hard
  shade_strength: 0.5   # baked occlusion and edge wear in the vertex colour (0 switches it off, up to 1)
```

Changes take effect from the next build. Per-program overrides (`sharp`, `smooth`, `part(..., shading=...)`) are in
`modelling-api.md`.

## Shading defects

The `shading` section of a build result says what the build fixed: `merged` vertices, `removed` zero-area faces and
`flipped` faces. Per part, it lists what it could not fix. Fix these in the program. Every part must be a closed
manifold solid that doesn't cut through itself: `openEdges`, `nonManifold`, `selfIntersecting` or `inward` above 0
fails validation (issue `not_solid`), though the model is still exported so you can look at it. Different parts may
overlap each other.

- **`openEdges`:** an open surface, such as a plane leaf. Give it thickness with SOLIDIFY, or use a closed primitive.
- **`nonManifold`:** edges shared by three or more faces (or by none), or pieces touching at a single vertex. They
  usually come from `join` of solids that share a face or an edge exactly, or from raw bmesh edits. Overlap joined
  pieces a little, or union them with `boolean(..., op="union")`; keep separate solids apart or make them parts.
- **`selfIntersecting`:** faces of a mesh that cut through other faces of the same mesh, usually from `join` of
  solids that overlap (a hub joined into spokes). Union them with `boolean(..., op="union")` or make them separate
  parts.
- **`inward`:** a closed piece still inside out. Build it from a closed primitive.
- **`bent`:** faces with 4+ corners that are not in one plane, which crease in flat shading. Keep the face flat, or
  triangulate it on purpose.

When the user says light looks wrong, check these counts first. In the view window, the user can switch off the baked
shade to tell its effect from the normals'.
