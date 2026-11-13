# Spec Delta

## Purpose

Turns an agent-written part program into clean low-poly multi-part geometry. The program defines explicit topology, symmetry, instances, joints and pivots. Each build is validated for fit and for likeness to the concept masks, then exported as a model the UI and game engines can load.

## ADDED Requirements

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
Every build SHALL be projected into the same orthographic views as the asset's picked turnaround. For each part and view it SHALL be scored against that part's mask, with overlap and signed size errors per axis.

#### Scenario: Wheel too small
- **WHEN** the compiled wheel's front-view projection is narrower than its mask
- **THEN** the score for wheel/front reports the overlap and a negative width error

### Requirement: Model export
Every successful build SHALL export a binary glTF (GLB) file. The file contains named part nodes, the hierarchy, pivots, instances and connection points as named empty nodes, in metres with Y up.

#### Scenario: Viewer loads export
- **WHEN** the user opens a successful build in the UI
- **THEN** the model is shown in an interactive 3D viewer with its part names listed
