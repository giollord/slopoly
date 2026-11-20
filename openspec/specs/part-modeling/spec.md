# part-modeling Specification

## Purpose
Turns an agent-written part program into clean low-poly multi-part geometry. The program defines explicit topology, symmetry, instances, joints and pivots. Each build is validated for fit and for likeness to the concept masks, then exported as a model the UI and game engines can load.

## Requirements

### Requirement: Part manifest
An asset's manifest SHALL list its parts and its symmetry planes. For each part it gives the parent, the primitive kind and the connections, with each connection's type: fixed, rotating around an axis, or sliding. Each part MAY also give a shape plan: `shape` (its shape character in words), `steps` (how it is built, in modelling operations) and `checks` (the views or close-ups that show it is right).

#### Scenario: Cart manifest
- **WHEN** the agent writes a manifest for the cart with bed, mirrored handles, axle and mirrored wheels, where the
  axle rotates around X, and runs `slopoly check`
- **THEN** the manifest passes, and a manifest that references unknown parent parts is reported as invalid

#### Scenario: Shape plan
- **WHEN** the smokestack part gives `shape: "flared funnel on a saddle, rolled rim"`, three `steps` and
  `checks: [side, "look:top"]`, and the agent runs `slopoly check`
- **THEN** the manifest passes, and a `checks` entry naming an unknown view is reported as invalid

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
- the intersection volume between each pair of parts, reported per pair with whether the program declared it
  (parts may overlap: an overlap SHALL NOT fail validation);
- that every declared connection touches within tolerance, and for one that doesn't, the nearest points on the part
  and on the part it connects to, and the gap between them;
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

#### Scenario: Floating cylinder
- **WHEN** a cylinder declared as touching the frame floats 0.043 m above it
- **THEN** the contact issue gives the nearest point on the cylinder, the nearest point on the frame and the 0.043 m
  gap

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
- **WHEN** the user opens a successful build in the view window
- **THEN** the model is shown in an interactive 3D viewer with its part names listed

#### Scenario: Standard viewer
- **WHEN** an exported model is opened in a standard glTF viewer
- **THEN** it shows the palette colours multiplied by the vertex shade, with the pack's flat or smooth shading

#### Scenario: Export to a game folder
- **WHEN** the agent runs `slopoly export gnome-village/cart --to <dir>`
- **THEN** `<dir>` holds the current build's GLB with the main palette embedded and each palette variant's texture as a
  separate image file

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
a mesh with a profile, using Blender curves. A path through only two control points SHALL also get that many
segments. It SHALL also be able to run Blender's mesh operations directly on a
shape's mesh. Any face left without a tag after a program SHALL be reported as an error naming the part.

#### Scenario: Bent handle
- **WHEN** a program makes a 6-sided handle along a curve through three control points with a resolution of 4
- **THEN** the handle bends smoothly through the points, with exactly 8 segments along its length

#### Scenario: Raw operation keeps tags
- **WHEN** a program extrudes faces of a tagged shape with a raw Blender operation
- **THEN** the new faces carry the source faces' tags, and the build succeeds

#### Scenario: Straight pole with rings
- **WHEN** a program makes a curve through two points with `smooth=False` and a resolution of 8
- **THEN** the pole has 8 segments along its length, so a vertex group ramp can taper and bend it

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

### Requirement: One triangle count
A build's result and report SHALL give one triangle count, the one the budget check uses. A build over budget SHALL
list an `over_budget` issue. The result SHALL include a compact list of parts with their triangles, so the agent can
see where the budget goes without opening the report.

#### Scenario: Over budget
- **WHEN** a build has 6,016 triangles against a budget of 6,000
- **THEN** the result says 6,016, lists `over_budget` under the validation issues, and names each part's triangles

### Requirement: Hidden reference surfaces
The 3D comparison SHALL NOT report reference volume that lies inside the build's closed volume as missing. Such
regions SHALL be marked `inside_build` with the parts that enclose them.

#### Scenario: Inside the frame
- **WHEN** the rough reference mesh has internal surfaces inside the build's solid frame box
- **THEN** that region is listed as `inside_build` with `frame`, and the missing share doesn't count it

### Requirement: 3D comparison with the reference mesh
When the variant's reference hero has a reference mesh, every build SHALL also be compared with it in 3D. The report
SHALL give the volume overlap of the whole model, the surface distance between them, and regions where the reference
has volume the model lacks, or the reverse, each with bounds in metres and the parts nearby.

#### Scenario: Cowcatcher plan
- **WHEN** the cowcatcher is built as straight parallel slats but the reference mesh is V-shaped in plan
- **THEN** the 3D comparison lists missing and extra regions at the cowcatcher's sides with their bounds, although no
  view's silhouette shows the difference

### Requirement: Robust join
`join` SHALL combine shapes whose faces repeat each other's vertices without failing. It SHALL merge or drop duplicate
faces. When it cannot make a valid mesh, it SHALL raise a program error that names the cause and the shapes involved.

#### Scenario: Joined ribs
- **WHEN** a program joins five rib shapes made of curves, jitter and boolean unions
- **THEN** the join succeeds, or the build fails with an error naming the duplicate faces and the ribs, never a raw
  Blender error

### Requirement: Jitter safe on thin walls
`jitter` SHALL limit each vertex's move to less than half the local wall thickness. It SHALL report a warning naming
the part when the jittered shape intersects itself.

#### Scenario: Jittered banner
- **WHEN** a program jitters a 0.05 m thick banner by 0.04
- **THEN** the moves are limited so opposite faces don't pass through each other, and the part stays a closed solid

### Requirement: Points on a surface
A part program SHALL be able to find the point and normal on a shape's surface where a ray from a given position and
direction meets it. A part can then be placed on a curved surface exactly.

#### Scenario: Spikes on an arched roof
- **WHEN** a program places roof spikes at the points where vertical rays from above meet the arched roof
- **THEN** each spike's base sits on the roof surface, and no spike sinks into the cab
