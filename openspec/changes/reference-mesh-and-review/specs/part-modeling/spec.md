# Spec Delta

## MODIFIED Requirements

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

## ADDED Requirements

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
