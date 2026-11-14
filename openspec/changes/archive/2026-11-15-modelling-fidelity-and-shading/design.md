## Context

See proposal.md for the motivation. Current state:

- **Builds.** A build runs `slopoly_model.runner` in a subprocess of the geometry worker: Blender 5.3 as the `bpy`
  module, CPU only.
  - The runner compiles the program, validates, scores silhouettes (projection with Pillow, no rendering) and exports
    a GLB through Blender's glTF exporter. The worker uploads the GLB and the report.
  - Faces are flat; Blender's default per-polygon shading makes the exporter split vertices per face.
  - Colours come from per-face UVs (UV0) into the pack's shared 256 px palette atlas. Variants swap the atlas.
- **Instancing.** Mirrored and repeated parts share meshes (`instance`, `mirror=`).
- **Scoring.** `silhouette.score_view` fits a uniform scale and offset per view, from the model's projected bounds to
  the view's `object` mask.
- **Agent.** It reads the build report through MCP `get_build_report` and views images only through `view_image`.
- **UI.** The asset page shows the GLB in `<model-viewer>` (a standard three.js glTF viewer).

## Goals / Non-Goals

**Goals:**

- The agent can see its model next to the views, framed exactly like the views.
- Shading is pack-wide and standard glTF: what `<model-viewer>` shows is what any glTF engine shows.
- Programs model with Blender's modifiers, vertex groups, curves and mesh operations; the library adds no modelling
  operations of its own.
- The agent builds parts by technique (notes with samples), not vertex by vertex.

**Non-Goals:**

- Geometry Nodes (a later change, if modifiers run out).

- Detail maps, a second UV set, layered vertex colours for custom shaders, export format choices (next change).
- Occlusion between different parts (see decision 4).
- Changing silhouette scoring itself.

## Decisions

### 1. Blender does the modelling; the library stops wrapping it

The library already delegates most operations to `bmesh.ops`; only `sweep` (about 50 lines) and the manifold3d
boolean round trip are our own geometry. This change removes both and opens Blender's tools to programs, keeping the
library to what is game-specific (parts, pivots, sockets, tags, budgets, scoring, export). `ngon` (a profile) and
`jitter` (a seeded vertex offset) stay as small conveniences.

**Shape = mesh + modifier stack.** A `Shape` keeps its bmesh and gains an ordered list of pending modifiers:

```python
trunk = prism(8, 0.12, 1.6, tag="bark")
trunk = trunk.modify("SIMPLE_DEFORM", deform_method="TAPER", factor=-0.3, group="top")
trunk = trunk.modify("BOOLEAN", object=grooves, operation="DIFFERENCE", solver="MANIFOLD")
```

- `modify(type, group=None, **settings)` appends a modifier; settings map 1:1 to the Blender modifier's properties,
  so Blender's own documentation is the reference and we write no per-modifier code. Shape-valued settings
  (`object`, `target`, `offset_object`) become temporary objects.
- The stack is applied when needed: when the shape goes into a `part`, a boolean, a raw operation or a copy that
  must be baked. Applying means a temporary object, the modifiers, and `evaluated_get(depsgraph)` read back into a
  bmesh. Until then the stack is just data, so the program stays non-destructive: the agent edits a setting and
  rebuilds.
- Unknown types or properties raise `ShapeError` with Blender's list of valid names.
- An allow-list keeps out modifiers that make no sense for static low-poly assets (cloth, ocean, particle system,
  skin, ...). It starts with: ARRAY, MIRROR, SCREW, SOLIDIFY, BOOLEAN, SHRINKWRAP, SIMPLE_DEFORM, DISPLACE, CAST,
  SMOOTH, CURVE, WAVE, WELD, DECIMATE, BEVEL, TRIANGULATE, SUBSURF, WIREFRAME, EDGE_SPLIT. REMESH is out because it
  drops face attributes (tags); LATTICE is out because it needs a lattice object (groups plus SIMPLE_DEFORM and CAST
  cover its uses).

**Cloning** is the Array modifier: linear, or radial with an `offset_object` rotated by 360°/count (the knowledge
note shows it). Mirror stays for symmetric halves inside a part; `instance`/`mirror=` still mirror whole parts.

**Vertex groups.** `group(shape, name, faces=..., where=..., weight=...)` creates a deform-layer group from a face
selector or a vertex predicate, with a constant weight or a function such as `ramp("y", 0, 1)` (a gradient along an
axis). Groups are used by `modify(..., group=)` and by `shape.move/rotate/scale(..., group=name)`, which moves each
vertex by its weight (`v + w * (T(v) - v)`), the same as proportional editing with a baked falloff.

**Curves.** `curve(points, resolution, profile, closed=False)` creates a Blender curve (auto handles, so it passes
through the points), sets `resolution_u`, uses the profile as the bevel shape, fills the caps, and converts it to a
mesh. Segment counts stay exact, and `sweep` is deleted.

**Raw operations.** Programs may call `bmesh.ops.*` on `shape.bm`, after the stack is applied (`shape.bm` applies it).

**Alternative rejected:** our own helpers per need (`around`, `circle`, a branch helper, ...). Each needs code,
tests and docs, and the agent keeps hitting the next missing one; Blender's modifiers already cover them.

### 1a. Face tags as an integer attribute

Tags are stored today as a bmesh string layer. Modifiers carry generic integer face attributes through their
output (new faces copy them from their source), but not reliably string ones. Tags become an INT face attribute
(`slopoly_tag`) indexing a per-model tag table, which also lets booleans carry the cutter's tags without our
manifold3d mapping.

- After each part is built, a check reports faces with no tag (index -1), naming the part.
- A geometry test runs every allow-listed modifier on a tagged shape and checks that every output face has a tag.

### 1b. Booleans with Blender's Manifold solver

Blender 4.5 and later ship the Manifold library as a solver of the Boolean modifier. `boolean(a, b, op)` stays as a
shortcut for `a.modify("BOOLEAN", object=b, operation=..., solver="MANIFOLD")`, then a limited dissolve as today. The
`to_manifold`/`from_manifold` code goes. If the solver misbehaves on some input, the Exact solver is the fallback
setting. manifold3d stays in the container for the validator's volumes, overlaps and gaps.

### 2. Shading through Blender's own sharp-edge model

- **The pack setting** goes to the runner as `shading: {mode, hardEdgeAngle, shadeStrength}`.
- **Flat mode** is today's behaviour.
- **Smooth mode:** the export sets polygons smooth and calls `Mesh.set_sharp_from_angle(angle)`. Program overrides
  are then applied:
  - `sharp(shape, faces)` and `smooth(shape, faces)` record edge flags in a bmesh layer, like `paint` records tags;
  - after the angle rule, flagged edges are forced hard or smooth;
  - `part(..., shading="flat"|"smooth")` overrides the mode per part.
- **Boundaries stay smooth.** The glTF exporter splits vertices at UV seams and at sharp edges, but writes the
  loop-normals Blender computed. Normals stay averaged across palette or UV boundaries (spec "Boundaries are not hard
  edges") without extra work. A test checks this on a two-role curved part.

**Alternative rejected:** computing normals ourselves in numpy. That duplicates Blender and risks disagreeing with what
it exports.

### 3. Vertex shade: Cycles AO bake into a colour attribute the material uses

- **Bake.** Per mesh, bake ambient occlusion with Cycles on the CPU into a byte colour attribute on face corners.
  It's low sample (about 16), with the AO distance a fraction of the mesh's size.
- **Edge wear.** Darken convex edges slightly: per-corner convexity from adjacent face normals, computed with numpy.
- **Combined value.** `shade = 1 - strength * (ao_term + wear_term)`, clamped to 0.35..1, stored as grey RGB.
- **Material.** The palette material multiplies the atlas by a Color Attribute node. Blender's glTF exporter writes an
  attribute the material uses as `COLOR_0`, and the Blender render in decision 4 shows the same result. glTF viewers
  multiply `COLOR_0` with the base colour.
- **Strength 0** skips the bake and the attribute.

**Alternatives rejected:**

- Baking shade into a per-asset texture: it breaks the shared atlas and variants.
- `occlusionTexture`: it needs a second UV set, which belongs to the next change.

### 4. AO is per mesh (self-occlusion only)

Meshes are shared by instances and mirrors, and a shared mesh can hold only one colour set. So each mesh is baked on its
own, at origin, without other parts: a bed's inner corners darken, but a wheel doesn't darken the bed.

**Why.** It keeps instancing intact, it's deterministic, and it's cheap.

**Alternative rejected:** whole-model AO. It needs unique meshes per placement, which would undo instancing.

### 5. Build renders with Cycles, framed by the silhouette fit

- **Framing.** For each view with an `object` mask, `score_view` already has the uniform scale and the offset that map
  the model onto the view. They are returned in the view's score.
- **Render.** The runner places an orthographic camera along the view direction: `ortho_scale = view_width / scale`,
  with the shift taken from the offset. It renders at the view's pixel size, so render and view overlay pixel for
  pixel.
- **Look.** Cycles (CPU, about 16 samples, denoiser off), a soft white world light plus one sun from the upper front-left (so form and shading read) and the "Standard" view
  transform, so colours read as palette × shade. Transparent film is composited on white like the views. About a
  second per view for low-poly models; four views per build.
- **Comparison image.** It has 3 panels: view, render, and silhouette difference (grey both, red model only, blue view
  only). Each panel is scaled to 384 px, giving 1152×384, which is cheap for the agent to view.
- **Storage.** The runner writes `render_<view>.png` and `compare_<view>.png`. The worker uploads them and sets
  `renderFileId` and `compareFileId` on each view's score in the report.
- **No masks.** A build without view masks has no renders; the silhouette entry says `views missing`.

**Alternative rejected:** Workbench or EEVEE. Both need a GPU or EGL context, which the headless CPU container
doesn't have. A Pillow painter's-algorithm render was also considered: it is cheap but shows no shading, and shading
is half of what the user wants to judge.

### 6. Data and API

- **Pack fields:** `ShadingMode` (Flat or Smooth, stored as a string), `HardEdgeAngle` (default 60, so 6–12-sided round parts shade round while box corners stay hard) and
  `ShadeStrength` (0..1, default 0.5). They come with a migration and `PackEdit` fields; existing packs get the
  defaults.
- **Build inputs:**
  - `BuildInputsAsync` adds `shading`;
  - each view in `views` already carries its `fileId`, which the worker downloads for the comparison.
- **MCP:** `get_pack` returns the settings, and `update_style` accepts them. The report passes through
  `get_build_report` unchanged; its description names `compareFileId` and points to `view_image`.

### 7. UI

- **Style tab.** A "Shading" panel has a Flat/Smooth toggle, the hard-edge angle (shown in smooth mode) and a
  shade-strength slider.
- **Asset page.** Under the viewer, a 2×2 grid of comparison images with each view's object IoU. It follows the build
  selector, and clicking an image opens it full size.

### 8. Agent

- **Iterate step** in `agent/CLAUDE.md`: for each view below the threshold, `view_image(compareFileId)` before
  changing the program. Then fix the parts that show red or blue.
- **Program reference:** `agent/docs/slopoly_model.md` documents `modify` (with the allow-list and links to Blender's
  modifier manual), `group`, `ramp`, group transforms, `curve`, raw `bmesh.ops` use, `sharp`, `smooth` and
  `part(shading=)`, plus the report's render fields. The docs test enforces that every public name is documented.
- **Modelling rules** in `agent/CLAUDE.md`: search the notes for the technique first; build from primitives plus
  modifiers, groups, cloning, mirroring and booleans; place vertices by hand only in 2D profiles and curve control
  points; keep segment, resolution and array counts low and check the triangle count.
- **Notes in two folders.** `knowledge/techniques/` holds how to model something; `knowledge/objects/` holds how to
  approach a concrete object type (proportions, which parts, which techniques, a full sample). Slugs carry the folder
  (`techniques/repeats`), so `KnowledgeService` lists both folders recursively and accepts one folder prefix out of
  those two; search ranks across both. The agent can write notes into either folder.
- **Technique notes.** Each says when to use it, the steps, the pitfalls and a runnable sample: blocking out from
  primitives, wheeled objects, surface texture from meshes, organic shapes, holes and openings, curved parts,
  repeats, lathed shapes, thin shells and panels, bevels and chamfers, rocks and chunks, foliage, ropes and chains,
  joints and moving parts, plus the existing hollow containers, wear and triangle budgets. The list is a start; the
  agent and the user add more through `write_knowledge`.
- **Object notes** start with the cart; more object types are added as they come up.

## Risks / Trade-offs

- **[Cycles is slow on the CPU for 4 renders plus AO bakes]** → Use low samples, small images (the views' 768 px), no
  denoiser and a time check in the cart run. If a build exceeds about 20 s, drop the render samples or render at
  half size and upscale the comparison.
- **[A camera fit that's off by a pixel shows false red and blue edges]** → Use the same scale and offset as the
  scoring, and a test that renders a synthetic model against its own projected mask and finds under 1 % difference.
- **[Smooth shading on 6–8 sided parts looks blobby]** → That's what the angle rule and `sharp()` are for. The
  knowledge notes show which edges to keep hard.
- **[AO per mesh misses contact shadows between parts]** → Accepted (decision 4); a later change can add
  whole-model AO for non-instanced parts.
- **[Modifiers dropping or mis-assigning face tags]** → Tags as an integer attribute (decision 1a), the untagged-face
  check, and a test per allow-listed modifier.
- **[Modifiers blowing the triangle budget]** (subdivision before displace, high array counts) → The existing budget
  check fails the build with the count; the notes show Decimate (planar) and low counts.
- **[The agent passing settings that exist but are wrong for low-poly]** → The notes give working values; errors
  echo Blender's own messages.
- **[Exporter vertex-colour behaviour differs between Blender versions]** → The colour attribute is wired through the
  material (decision 3), which the 4.2+ exporters export. A test reads `COLOR_0` back from the GLB.

## Migration Plan

No backward compatibility: existing models and programs are not kept working. An EF migration adds the pack columns
with defaults; old programs that use `sweep` simply fail if rebuilt, and the next agent run writes new ones.
