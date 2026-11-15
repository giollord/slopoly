# Spec Delta

## MODIFIED Requirements

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
