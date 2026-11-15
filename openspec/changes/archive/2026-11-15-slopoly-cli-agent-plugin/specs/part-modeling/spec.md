# Spec Delta

## MODIFIED Requirements

### Requirement: Fit validation
Every build SHALL produce a validator report that checks:
- the intersection volume between each pair of parts, reported per pair with whether the program declared it
  (parts may overlap: an overlap SHALL NOT fail validation);
- that every declared connection touches within tolerance;
- that no part is disconnected from the root;
- the total polygon count, against the pack's budget;
- that every part's mesh is a closed manifold solid: no open edges, no non-manifold edges or vertices, no faces
  cutting through other faces of the same mesh, and no piece inside out.

#### Scenario: Overlap detected
- **WHEN** the bed and a handle intersect by more than the tolerance without being declared as overlapping
- **THEN** the report marks the pair as not ok with the intersection volume, and the build can still be validated

#### Scenario: Clean build
- **WHEN** all checks pass
- **THEN** the build is marked validated

#### Scenario: Overlapping solids in one mesh
- **WHEN** a part's shape joins a hub that overlaps its spokes into one mesh
- **THEN** the report lists the part's self-intersecting faces under `not_solid`, and the build is not validated

#### Scenario: Non-manifold part
- **WHEN** a wheel is joined from solids that share edges exactly, leaving edges with more than two faces
- **THEN** the report lists a `not_solid` issue naming the wheel parts and their counts, and the build is not
  validated

### Requirement: Build renders beside the views
Every build of an asset whose picked hero has views SHALL be rendered orthographically from the views' four
directions, at the views' pixel size, in its palette colours and shading. Per view it SHALL also store a comparison
image of the reference view, the render and their differences. Renders and comparisons SHALL be files listed in the
build's report.

Per view, the report SHALL also list detail regions, so features that barely change the silhouette score are not
missed: view areas the model doesn't cover (`missing`), model areas outside the view (`extra`), areas where both cover
but the colours differ (`colour`), and lines in the view with no line near them in the render (`edge`). Each region
SHALL have a number shown on the comparison image, a box relative to the object, its size, the part masks it
overlaps and its colours. Small regions and differences along the outline SHALL be ignored.

#### Scenario: Cart comparison
- **WHEN** a cart build is scored against its hero's views
- **THEN** its report lists four renders and four comparison images
- **AND** each comparison shows the reference view, the model render, and the silhouette difference with model-only
  and view-only pixels in distinct colours, so the side comparison shows where straight handles miss the view's
  curved ones

#### Scenario: No views yet
- **WHEN** an asset without a picked hero's views is built
- **THEN** the build succeeds without renders or comparisons, and the report says why they are missing

#### Scenario: Feature inside the silhouette
- **WHEN** the view shows a dark iron band across a wooden body and a frame of boards on its front, and the model is
  plain wood with the same outline
- **THEN** the front view's detail lists a `colour` region over the band and `edge` regions over the frame's lines,
  even though the object IoU is high

#### Scenario: Thin missing part
- **WHEN** the view has a thin handle that the model lacks
- **THEN** the detail lists a `missing` region over it, overlapping the handle's part mask

### Requirement: Part manifest
An asset's manifest SHALL list its parts and its symmetry planes. For each part it gives the parent, the primitive kind and the connections, with each connection's type: fixed, rotating around an axis, or sliding.

#### Scenario: Cart manifest
- **WHEN** the agent writes a manifest for the cart with bed, mirrored handles, axle and mirrored wheels, where the
  axle rotates around X, and runs `slopoly check`
- **THEN** the manifest passes, and a manifest that references unknown parent parts is reported as invalid

### Requirement: Model export
Every successful build SHALL export a binary glTF (GLB) file. The file contains named part nodes, the hierarchy,
pivots, instances, connection points as named empty nodes, palette UVs and the main palette material, in metres with
Y up. Its normals SHALL follow the pack's shading settings, and it SHALL carry the baked vertex shade as the standard
vertex colour. A standard glTF viewer SHALL display it correctly without custom shaders.

#### Scenario: Viewer loads export
- **WHEN** the user opens a successful build in the view window
- **THEN** the model is shown in an interactive 3D viewer with its part names listed

#### Scenario: Standard viewer
- **WHEN** an exported model is opened in a standard glTF viewer
- **THEN** it shows the palette colours multiplied by the vertex shade, with the pack's flat or smooth shading

#### Scenario: Export to a game folder
- **WHEN** the agent runs `slopoly export gnome-village/cart --to <dir>`
- **THEN** `<dir>` holds the current build's GLB with the main palette embedded and each palette variant's texture as a
  separate image file

### Requirement: Blender file per build
Every successful build SHALL also save a Blender file of the model. It holds the same named part objects, hierarchy,
pivots, sockets, joints, normals, hard edges and palette material as the GLB, in metres in Blender's own Z-up
orientation. The palette texture SHALL be linked as an external image by relative path, not packed into the file.

#### Scenario: Open in Blender
- **WHEN** the user opens a cart build's Blender file in Blender
- **THEN** it shows the cart's named parts in their hierarchy, with the axle-and-wheels part's pivot and joint, in the
  palette colours with the pack's shading

#### Scenario: Older build without a Blender file
- **WHEN** a build has no Blender file and the agent exports it with `--blend`
- **THEN** the export fails, saying the build has no Blender file and that rebuilding its program makes one

### Requirement: Blender file download
`slopoly export <target> --blend --to <dir>` SHALL copy the build's Blender file to `<dir>` with the pack's current
main palette and palette variant textures, which the file references by relative path.

#### Scenario: Palette edited after the build
- **WHEN** the user changes a palette colour after a build and then exports that build with `--blend`
- **THEN** the Blender file opened from `<dir>` shows the new colour without a rebuild

#### Scenario: Switch to a palette variant in Blender
- **WHEN** the user points the palette image in the opened file to the exported `palette_autumn.png`
- **THEN** the model shows the autumn colours

## ADDED Requirements

### Requirement: Safe bevels
`bevel` SHALL bevel only edges where two faces meet at a given angle or more (30 degrees by default), clamp widths
where bevels would overlap, and triangulate bevel faces that come out bent. It SHALL raise a program error, not
return the shape, when the result would have new non-manifold edges or vertices outside the input's bounds. A face
selected by direction SHALL have its normal within 30 degrees of that direction.

#### Scenario: Bevelled seamed box
- **WHEN** a box with wrap-around seam grooves is bevelled
- **THEN** the result has no open, non-manifold or bent faces, and stays inside the box's bounds

#### Scenario: Inset after bevel
- **WHEN** a bevelled box's "top" is inset
- **THEN** only the flat top is inset, and no vertex rises above the top
