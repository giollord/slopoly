## Why

The cart run stopped at a mean object IoU of 0.785, below the 0.8 bar. The agent's straight handle sweeps and solid
wheel discs couldn't match the hero's curved handles and spoked wheels. It also never saw its own model: it worked
from numbers alone, so it couldn't tell what differed. Separately, every asset is flat-shaded with flat palette
colours. Flat shading is one valid look, but the user's games need a pack-wide choice between flat and smooth shading
with hard edges where they belong, and some soft shading depth (ambient occlusion, worn edges). All of this must keep
the shared palette atlas and its variants working.

## What Changes

- **Model with Blender's own tools instead of wrapping them.** The part library keeps only what is game-specific
  (parts, pivots, sockets, palette tags, budgets, scoring, export) and stops re-implementing modelling operations:
  - **Modifier stacks** on shapes: Blender modifiers (array, mirror, screw, solidify, boolean, shrinkwrap, simple
    deform, displace, cast, smooth, lattice, weld, decimate, bevel, ...) are added by name with their settings and
    are applied when the part is built. Modifiers that need another object (boolean cutter, shrinkwrap target, array
    offset) take a shape.
  - **Vertex groups**: named groups of faces or vertices, with optional weights (for example a gradient along an
    axis), used to limit a modifier to part of a shape and to move, rotate or scale a whole group at once.
  - **Curves**: smooth paths through control points, built as Blender curves with a profile and a set resolution,
    then turned into meshes. They replace our own `sweep`.
  - **Raw Blender operations**: programs may call `bmesh.ops` directly on a shape's mesh. Face tags carry through,
    and a check flags any untagged face.
  - Booleans use Blender's boolean modifier (Manifold solver) instead of our manifold3d round trip.
- **Modelling rulesets with samples.** Knowledge notes give a technique per kind of problem, each with a runnable
  sample, so the agent builds from primitives plus modifiers, cloning and booleans instead of placing vertices:
  - wheeled objects (rim, spokes and hub; mirrored axles);
  - surface texture from meshes (bark, planks, stones: wavy strips shrinkwrapped onto a surface, then cut or added);
  - organic look (deforming a vertex group: a box bent and tapered into a branch);
  - holes and openings (boolean cut-outs, and inset plus extrude);
  - curved and bent parts (handles, arches, ropes);
  - repeats (array and radial array, mirror).
  The agent's instructions gain modelling rules: start from these techniques, prefer modifiers to hand-placed
  vertices, and keep segment and repeat counts low.
- **Build renders beside the views.** Each build is rendered orthographically from the same four directions as the
  hero's views (front, side, top and back), in palette colours with its shading, and the renders are stored as files.
  A comparison image per view (reference view, model render, silhouette difference) lets the agent see what differs,
  and the asset page shows it to the user.
- **Shading modes per pack.**
  - **Flat:** today's look, every edge hard.
  - **Smooth:** normals averaged, with edges sharper than a pack-wide hard-edge angle kept hard.
  - Programs can force hard or smooth edges on selected faces, and a part can override the pack's mode.
  - Vertices split for palette or UV boundaries keep their averaged normals, so they don't show as hard edges.
- **Vertex shade.** Each build bakes a greyscale shade (ambient occlusion plus a little edge wear) into the standard
  glTF vertex colour (`COLOR_0`). Standard viewers and engines multiply it with the palette atlas, so the in-app
  preview and any glTF engine show it, and palette variants keep working. The shade can be switched off and its
  strength set per pack.
- **Cart re-run.** Take the cart to the stop rule (mean object IoU at least 0.8, every view at least 0.7) with
  modifiers, the techniques and the renders, and record the outcome.

Detail maps (a second UV set), the layered vertex-colour export for custom shaders, and export format choices belong
to the next change.

## Capabilities

### New Capabilities

- `surface-shading`: the pack's shading mode (flat or smooth), the hard-edge angle and the program and part overrides,
  plus the baked vertex shade, its strength and switch.

### Modified Capabilities

- `part-modeling`:
  - new requirements for modifier stacks, vertex groups, curves and raw Blender operations in programs, and for
    build renders beside the views;
  - model export gains normals per the shading mode and the vertex shade.
- `design-agent`: new requirements that the agent compares its build with the views by viewing the comparison images
  through the dedicated image tool, and that it models by techniques (primitives, modifiers, cloning, booleans)
  rather than by vertices.
- `knowledge-base`: the shipped notes include modelling rulesets with runnable samples for the listed techniques.
- `studio-ui`: the asset page shows the per-view comparison of a build, and the pack's style tab edits the shading
  settings.

## Impact

- **Geometry** (`geometry/slopoly_model`, `containers/geometry`):
  - shapes gain modifier stacks, vertex groups and Blender curves; our `sweep` and the manifold3d boolean code are
    removed; face tags become an integer face attribute so modifiers carry them; `sharp`/`smooth` face selectors;
  - shading and normals in the export, and a vertex-shade bake (Blender, in the existing bpy container);
  - an orthographic render of each build with the comparison images; build outputs gain render file ids.
- **API and data:** pack fields for shading mode, hard-edge angle and shade strength, plus a migration. Build inputs
  carry the shading settings and the views; build reports carry the render and comparison file ids. The MCP
  `get_build_report` lists the comparison file ids.
- **UI:** shading settings on the pack's style tab, and the per-view comparison on the asset page.
- **Agent:** `agent/CLAUDE.md` (modelling rules; iterate step: look at the comparisons) and
  `agent/docs/slopoly_model.md` (modifiers, vertex groups, curves, raw `bmesh.ops`, shading, `sharp`/`smooth`).
- **Knowledge:** six technique notes with samples, run by the docs test; existing notes updated to the new API.
- **No new dependencies:** Blender (bpy) already models, renders and bakes in the geometry container. manifold3d may
  be dropped once booleans move to Blender.
