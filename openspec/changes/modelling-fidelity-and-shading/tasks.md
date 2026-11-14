# Tasks

## 1. Blender modelling in programs

- [ ] 1.1 Move face tags from the string layer to an INT face attribute (`slopoly_tag`) with a per-model tag table,
  and add the untagged-face check after each part. Verify: the existing geometry tests pass unchanged, and a new test
  shows that a face with no tag fails the build with the part's name.
- [ ] 1.2 Add `Shape.modify(type, group=None, **settings)` with the allow-list. The stack is applied lazily (on
  `part`, boolean, `shape.bm`, copy), and shape-valued settings become temporary objects. Unknown types or settings
  raise `ShapeError`. Verify: geometry tests show that a radial Array of a spoke gives 6 spokes at 60° steps with
  gaps in the side silhouette; that every allow-listed modifier keeps a tag on every output face; that an unknown
  type or setting fails with its name; and that an unapplied stack costs nothing until it is used.
- [ ] 1.3 Add vertex groups: `group(shape, name, faces=, where=, weight=)`, `ramp(axis, a, b)`, `modify(..., group=)`
  and weighted `move/rotate/scale(..., group=)`. Verify: a geometry test shows that a box with a 0-to-1 ramp group,
  bent and tapered via SIMPLE_DEFORM on the group, keeps its base fixed and narrows at the tip; another shows that
  scaling a "top" group moves only those vertices.
- [ ] 1.4 Add `curve(points, resolution, profile, closed=False)` on Blender curves, and delete `sweep`, moving its
  callers and tests to `curve`. Verify: a geometry test shows that a 3-point curve with a resolution of 8 gives
  exactly 8 segments through each point, and that a closed curve is watertight.
- [ ] 1.5 Move `boolean` to the Boolean modifier with the Manifold solver (Exact as a fallback setting), delete
  `to_manifold`/`from_manifold`, and drop manifold3d from the container if nothing else uses it. Verify: the
  existing boolean tests pass, cutter tags carry onto the cut faces, and the bark sample (strips shrinkwrapped and
  subtracted) shows grooves tagged with the strips' role.
- [ ] 1.6 Allow raw `bmesh.ops` on `shape.bm` in programs. Verify: a geometry test shows that a raw
  `extrude_face_region` keeps the source tags and the build succeeds.
- [ ] 1.7 Document `modify` (allow-list, Blender manual links), `group`, `ramp`, group transforms, `curve` and raw
  operations in `agent/docs/slopoly_model.md`. Verify: the docs test (every public name documented) passes.

## 2. Modelling rulesets and samples

- [ ] 2.1 Extend the docs test so every code block in `knowledge/*.md` builds, and the notes test fails on the first
  broken sample with its note's name. Verify: a deliberately broken sample fails the test with the right message.
- [ ] 2.2 Write the technique notes `wheeled-objects`, `surface-texture`, `organic-shapes`, `holes-and-openings`,
  `curved-parts` and `repeats`, each with when to use it, the steps, the pitfalls and a runnable sample. Verify: the
  notes test builds every sample within its triangle budget, and searches for "spoked wheel", "branch", "bark" and
  "hole" return the matching notes.
- [ ] 2.3 Update `hollow-containers`, `wear-and-imperfections` and `triangle-budgets` to the new API (curves,
  modifiers, groups). Verify: the notes test passes.
- [ ] 2.4 Add the modelling rules to `agent/CLAUDE.md`: technique notes first; primitives plus modifiers, groups,
  cloning, mirroring and booleans; vertices by hand only in profiles and curve control points; low counts. Verify:
  the agent worker tests pass, and the instructions contain the rules.

## 3. Pack shading settings (data, API, MCP)

- [ ] 3.1 Add `ShadingMode` (Flat or Smooth, default Flat), `HardEdgeAngle` (default 40) and `ShadeStrength`
  (default 0.5, range 0..1) to the pack, with an EF migration, `PackEdit` fields and validation. Verify: a .NET test
  shows that a new pack has the defaults, that an edit persists, and that out-of-range values are rejected.
- [ ] 3.2 Pass `shading: {mode, hardEdgeAngle, shadeStrength}` in build inputs (`BuildInputsAsync`). Verify: a .NET
  test asserts the build job's inputs carry the pack's shading.
- [ ] 3.3 MCP: `get_pack` returns the shading settings and `update_style` accepts them. Verify: `McpToolsTests`
  round-trips a change of mode and strength.

## 4. Shading in the export

- [ ] 4.1 Smooth mode in `export.py`: set polygons smooth and apply `set_sharp_from_angle(hardEdgeAngle)`. Flat mode
  stays as it is today. Verify: geometry tests read the GLB back with trimesh and check that a smooth 8-sided
  cylinder shares normals around its side, that its caps stay hard, and that a flat build has per-face normals.
- [ ] 4.2 Add the overrides `sharp(shape, faces)`, `smooth(shape, faces)` and `part(..., shading=)`. The edge flags
  are stored on the shape and applied after the angle rule. Verify: geometry tests show that a smooth-mode box with
  `smooth()` on all faces has shared corner normals, that `sharp()` on a cylinder seam makes that edge hard, and that
  `part(shading="flat")` in a smooth pack exports per-face normals.
- [ ] 4.3 Check that palette and UV boundaries are not hard edges. Verify: a geometry test builds a curved part
  painted with two roles in smooth mode and confirms that the split vertices along the role boundary have identical
  normals.
- [ ] 4.4 Document `sharp`, `smooth`, `part(shading=)` and the pack shading in `agent/docs/slopoly_model.md`. Verify:
  the docs test passes.

## 5. Baked vertex shade

- [ ] 5.1 Bake per-mesh AO (Cycles CPU, about 16 samples) and convex-edge wear into a byte colour attribute on
  corners: `shade = 1 - strength * (ao + wear)`, clamped to 0.35..1, grey. At strength 0, skip the bake and the
  attribute. Verify: geometry tests show that the inner bottom of an open box is darker than its outer top, that
  instanced or mirrored parts share one mesh with one colour set, and that a strength-0 build has no `COLOR_0`.
- [ ] 5.2 Multiply the palette texture by a Color Attribute node in the material, so the exporter writes `COLOR_0`.
  Verify: a geometry test reads `COLOR_0` from the GLB with trimesh and checks that its values match the attribute.
- [ ] 5.3 Report the bake time and the vertex count in the build report. Verify: a geometry test checks that the
  fields are present, and the stack's cart build shows them.

## 6. Build renders and comparisons

- [ ] 6.1 Return the fitted scale and offset from `silhouette.score_view`. Verify: the existing silhouette tests
  pass, and a new test checks that the values reproduce the fitted bounds.
- [ ] 6.2 Render each view with an orthographic Cycles camera framed from that fit, at the view's pixel size (uniform
  white world, Standard view transform, white background). Verify: a geometry test renders a synthetic model against
  its own projected mask, and the silhouettes differ in under 1 % of pixels.
- [ ] 6.3 Compose `compare_<view>.png`: the view, the render, and their difference (grey both, red model only, blue
  view only), each scaled to 384 px. Verify: a geometry test checks that the image is 1152×384 and that a model
  shifted on purpose shows red and blue pixels on the correct sides.
- [ ] 6.4 Worker: download the view images given in the build inputs, upload the renders and comparisons, and set
  `renderFileId` and `compareFileId` on each view's score. Without view masks, skip the renders and report why.
  Verify: geometry worker tests with a fake staging check that both cases produce the right report shape.
- [ ] 6.5 Name `compareFileId` and `view_image` in the `get_build_report` tool description, and confirm that reports
  carry only ids. Verify: `McpToolsTests` asserts that the report has file ids and no image data.

## 7. UI

- [ ] 7.1 On the style tab, add a Shading panel: a Flat/Smooth toggle, a hard-edge angle field (smooth only) and a
  shade-strength slider, saved through `PackEdit`. Verify: in the running app, the settings are changed, survive a
  reload, and appear in the next build's inputs.
- [ ] 7.2 On the asset page, under the viewer, add a 2×2 comparison grid with the object IoU per view. It follows the
  build selector, and clicking an image opens it full size. Verify: in the running app, the cart page shows four
  comparisons, and switching to an older build changes them.

## 8. Agent

- [ ] 8.1 In the iterate step of `agent/CLAUDE.md`, have the agent call `view_image(compareFileId)` for each view below
  the threshold, then fix the parts that show red or blue. Point it to the technique notes. Verify: the
  agent worker tests pass, and the instructions mention the comparison step.

## 9. End-to-end: the cart

- [ ] 9.1 Run all suites: `dotnet test Slopoly.Tests`, plus the compose `tests`, `geometry-tests` and `agent-tests`.
  Verify: they all pass.
- [ ] 9.2 With the stack running, re-run the cart's design agent against its hero's views, in a smooth-shaded pack
  with shade on. Verify: mean object IoU ≥ 0.8 with every view ≥ 0.7, the handles are curves, the wheels are spoked by a radial array, the program uses technique notes rather than
  hand-placed vertices,
  the four comparisons show on the asset page, the model looks right in `<model-viewer>`, and a build takes under
  about 20 s.

## Workflow follow-up

- Archive the change with `openspec-archive-change` after review.
- Change 2: detail maps (UV1), the layered export and the choice of export format.
