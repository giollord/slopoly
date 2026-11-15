## ADDED Requirements

### Requirement: Blender file per build
Every successful build SHALL also save a Blender file of the model. It holds the same named part objects, hierarchy,
pivots, sockets, joints, normals, hard edges and palette material as the GLB, in metres in Blender's own Z-up
orientation. The palette texture SHALL be linked as an external image by relative path, not packed into the file.

#### Scenario: Open in Blender
- **WHEN** the user opens a cart build's Blender file in Blender
- **THEN** it shows the cart's named parts in their hierarchy, with the axle-and-wheels part's pivot and joint, in the
  palette colours with the pack's shading

#### Scenario: Older build without a Blender file
- **WHEN** a build was made before Blender files existed
- **THEN** the asset page says the build has no Blender file and that rebuilding its version makes one

### Requirement: Blender file download
The asset page SHALL offer a "Blender" download for the selected build, separate from Export. It downloads a zip of
the Blender file and the pack's current main palette and palette variant textures, which the file references by
relative path.

#### Scenario: Palette edited after the build
- **WHEN** the user changes a palette colour after a build and then downloads that build's Blender file
- **THEN** the Blender file opened from the zip shows the new colour without a rebuild

#### Scenario: Switch to a palette variant in Blender
- **WHEN** the user points the palette image in the opened file to the zip's `palette_autumn.png`
- **THEN** the model shows the autumn colours
