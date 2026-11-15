# part-modeling Specification

## Purpose
Turns an agent-written part program into clean low-poly multi-part geometry. The program defines explicit topology, symmetry, instances, joints and pivots. Each build is validated for fit and for likeness to the concept masks, then exported as a model the UI and game engines can load.

## Requirements

### Requirement: Part manifest
An asset's manifest SHALL list its parts and its symmetry planes. For each part it gives the parent, the primitive kind and the connections, with each connection's type: fixed, rotating around an axis, or sliding.

#### Scenario: Cart manifest
- **WHEN** the agent stores a manifest for the cart with bed, mirrored handles, axle and mirrored wheels, where the axle rotates around X
- **THEN** the manifest is saved on the asset and rejected if it references unknown parent parts

### Requirement: Part program compilation
A part program SHALL compile into one named mesh per part. Round primitives SHALL use the segment count the program states. Faces SHALL keep quads where the operations produce quads.

#### Scenario: Low-poly wheel
- **WHEN** a program defines a wheel as an 8-sided prism with a hub
- **THEN** the compiled wheel has exactly 8 side faces around its rim

#### Scenario: Program error
- **WHEN** a program raises an error during compilation
- **THEN** the build fails with the error message and the line it came from

### Requirement: Symmetry and instances
Parts declared mirrored SHALL be produced as exact mirror images. Repeated parts declared as instances of one definition SHALL be exported as instances, not copies.

#### Scenario: Mirrored handle
- **WHEN** the left handle is declared mirrored across X
- **THEN** the right handle's vertices are the left handle's vertices with X negated

#### Scenario: Bench planks
- **WHEN** a bench program places 30 planks from 3 plank definitions
- **THEN** the exported model contains 3 meshes and 30 instances

### Requirement: Pivots for moving parts
Parts with rotating or sliding connections SHALL be exported as separate nodes whose origin and axis match the connection, so an engine can rotate or slide them directly.

#### Scenario: Wheel spin
- **WHEN** the cart is exported
- **THEN** the axle node's origin lies on the axle axis, the wheels are its children, and rotating the axle node turns the wheels in place

### Requirement: Fit validation
Every build SHALL produce a validator report that checks:
- the intersection volume between each pair of parts, against a tolerance;
- that every declared connection touches within tolerance;
- that no part is disconnected from the root;
- the total polygon count, against the pack's budget.

#### Scenario: Overlap detected
- **WHEN** the bed and a handle intersect by more than the tolerance
- **THEN** the report marks the pair as failing with the intersection volume

#### Scenario: Clean build
- **WHEN** all checks pass
- **THEN** the build is marked validated

### Requirement: Silhouette scoring
Every build SHALL be projected into the orthographic views of the asset's picked hero, in the views' known orientation. For each view it SHALL be scored on the whole-object silhouette, with overlap and signed size errors per axis. For each part and view it SHALL be scored against that part's mask in the same way. The whole-object score is the primary measure of likeness.

#### Scenario: Wheel too small
- **WHEN** the compiled wheel's front-view projection is narrower than its mask
- **THEN** the score for wheel/front reports the overlap and a negative width error

#### Scenario: Object score
- **WHEN** a build's overall proportions match the hero's views but one small part is misplaced
- **THEN** the whole-object scores are high in every view and only that part's scores are low

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
A part program SHALL be able to build a smooth path through control points with a stated resolution (segments per
span between control points) and turn it into
a mesh with a profile, using Blender curves. It SHALL also be able to run Blender's mesh operations directly on a
shape's mesh. Any face left without a tag after a program SHALL be reported as an error naming the part.

#### Scenario: Bent handle
- **WHEN** a program makes a 6-sided handle along a curve through three control points with a resolution of 4
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
