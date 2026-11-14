## ADDED Requirements

### Requirement: Modifier stacks in part programs
A part program SHALL be able to add Blender modifiers to a shape by type name with their settings, in order, and the
stack SHALL be applied when the shape is used in a part, a boolean or a raw operation. Modifiers that need another
object SHALL take a shape for it. A modifier SHALL be limitable to a vertex group. Face tags SHALL carry through every
modifier onto the faces it creates or changes, and an unknown modifier type or setting SHALL fail the build with an
error that names it.

#### Scenario: Spoked wheel by cloning
- **WHEN** a program builds a wheel from a ring rim and one spoke with a radial array of 6
- **THEN** the wheel is one shape with 6 evenly spaced spokes, gaps between them visible from the side, and every
  spoke face keeps the spoke's tag

#### Scenario: Bark texture
- **WHEN** a program shrinkwraps a few wavy extruded strips onto a trunk with an offset and subtracts them with a
  boolean modifier
- **THEN** the trunk shows shallow grooves where the strips were, and the groove faces carry the strips' tag

#### Scenario: Unknown modifier
- **WHEN** a program adds a modifier type or setting that Blender doesn't have
- **THEN** the build fails with an error naming the type or setting

### Requirement: Vertex groups
A part program SHALL be able to create named vertex groups from face selectors or vertex conditions, with optional
weights such as a gradient along an axis. It SHALL be able to move, rotate or scale a group at once, weighted by its
weights, and to limit modifiers to a group.

#### Scenario: Box into branch
- **WHEN** a program takes a long box, weights a group from 0 at the base to 1 at the tip, and applies a bend and a
  taper limited to that group
- **THEN** the base stays in place while the shape curves and narrows towards the tip

#### Scenario: Group transform
- **WHEN** a program scales the group of a crate's top faces by 1.2
- **THEN** only those vertices move, and the rest of the crate is unchanged

### Requirement: Curves and raw Blender operations
A part program SHALL be able to build a smooth path through control points with a stated resolution and turn it into
a mesh with a profile, using Blender curves. It SHALL also be able to run Blender's mesh operations directly on a
shape's mesh. Any face left without a tag after a program SHALL be reported as an error naming the part.

#### Scenario: Bent handle
- **WHEN** a program makes a 6-sided handle along a curve through three control points with a resolution of 8
- **THEN** the handle bends smoothly through the points, with exactly 8 segments along its length

#### Scenario: Raw operation keeps tags
- **WHEN** a program extrudes faces of a tagged shape with a raw Blender operation
- **THEN** the new faces carry the source faces' tags, and the build succeeds

### Requirement: Build renders beside the views
Every build of an asset whose picked hero has views SHALL be rendered orthographically from the views' four
directions, at the views' pixel size, in its palette colours and shading. Per view it SHALL also store a comparison
image of the reference view, the render and their silhouette difference. Renders and comparisons SHALL be files listed
in the build's report.

#### Scenario: Cart comparison
- **WHEN** a cart build is scored against its hero's views
- **THEN** its report lists four renders and four comparison images
- **AND** each comparison shows the reference view, the model render, and the silhouette difference with model-only
  and view-only pixels in distinct colours, so the side comparison shows where straight handles miss the view's
  curved ones

#### Scenario: No views yet
- **WHEN** an asset without a picked hero's views is built
- **THEN** the build succeeds without renders or comparisons, and the report says why they are missing

## MODIFIED Requirements

### Requirement: Model export
Every successful build SHALL export a binary glTF (GLB) file. The file contains named part nodes, the hierarchy,
pivots, instances, connection points as named empty nodes, palette UVs and the main palette material, in metres with
Y up. Its normals SHALL follow the pack's shading settings, and it SHALL carry the baked vertex shade as the standard
vertex colour. A standard glTF viewer SHALL display it correctly without custom shaders.

#### Scenario: Viewer loads export
- **WHEN** the user opens a successful build in the UI
- **THEN** the model is shown in an interactive 3D viewer with its part names listed

#### Scenario: Standard viewer
- **WHEN** an exported model is opened in a standard glTF viewer
- **THEN** it shows the palette colours multiplied by the vertex shade, with the pack's flat or smooth shading
