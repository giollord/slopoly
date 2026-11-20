# reference-mesh Specification

## Purpose
Gives every reference hero a rough 3D mesh at the asset's real size, so views, close-ups, measurements, segmentation
and build comparisons all work from one consistent 3D reference.

## Requirements

### Requirement: Reference mesh from a hero
For a picked hero, the system SHALL generate a rough 3D mesh with vertex colours, using an image-to-3D model on the
user's ComfyUI. The mesh SHALL be stored with the hero's views, linked to the hero, with the generator name and seed
in its metadata.

#### Scenario: Locomotive mesh
- **WHEN** a views job runs for the picked locomotive hero
- **THEN** a GLB mesh of the locomotive is stored next to its views, and the views metadata names the generator and
  seed

#### Scenario: Missing generator model
- **WHEN** the mesh generator's model file is not on the user's ComfyUI
- **THEN** the job fails with a `missing_model` error naming the file, and `slopoly retry` reruns it after the model
  is fetched

### Requirement: Real-size reference
The reference mesh SHALL be placed in the asset's frame: front towards +Z, Y up, standing on y = 0, centred on X and
Z, and scaled in metres. The scale SHALL come from the asset's stated size (its longest dimension or a named axis)
when given. Otherwise the CLI estimates it and marks it `assumed`. Changing the size SHALL rescale the mesh without
regenerating it.

#### Scenario: Stated length
- **WHEN** the locomotive asset states a length of 9 m along Z and its views are made
- **THEN** the reference mesh spans 9 m along Z, stands on y = 0, and the views result reports the scale as `given`

#### Scenario: Size changed later
- **WHEN** the user changes the locomotive's length to 10 m
- **THEN** the reference mesh, views and measurements are rescaled to 10 m without a new generation job

### Requirement: Close-up renders
`slopoly look <target>` SHALL render the variant's reference mesh orthographically or in perspective from a named
direction or a yaw and pitch. It can zoom to a box in metres or to a part's region. It can also render the current
build from the same camera beside it. The result SHALL give the image paths and the camera, never image data.

#### Scenario: Cowcatcher from above
- **WHEN** the agent runs `slopoly look orcish/locomotive --from top --region cowcatcher`
- **THEN** an image of the reference mesh's cowcatcher region seen from above is written, and the result gives its
  path, the camera and the region's bounds in metres

#### Scenario: Build beside the reference
- **WHEN** the agent adds `--with-build`
- **THEN** the current build is rendered from the same camera and both paths are returned

### Requirement: Metric measurements
Views, segmentation and `look` results SHALL map image pixels to metres. For each image they SHALL give the model axis
along the image's x and y, the metres per pixel, and the image row of the ground. Part regions SHALL be reported with
bounds in metres.

#### Scenario: Measure the stack
- **WHEN** the agent reads the side view of the locomotive
- **THEN** the result gives metres per pixel and the ground row, so a pixel distance converts to metres without
  guessing

### Requirement: Generator chosen by benchmark
The default mesh generator SHALL be chosen by a recorded comparison of the candidate local models: the current splat
generator (its splat turned into a mesh) and the image-to-3D models of the shipped ComfyUI template. They are compared on the same picked heroes,
including the cart and the locomotive. The comparison SHALL cover agreement with the hero silhouette, thin parts
kept, time and GPU memory.

#### Scenario: Recorded choice
- **WHEN** the benchmark is complete
- **THEN** the change notes record each candidate's measurements, the chosen generator and why, and the shipped
  workflow uses the chosen generator by default

#### Scenario: Generator selectable
- **WHEN** the user runs `slopoly gen views <asset> --generator <name>` with another shipped candidate
- **THEN** the reference mesh is made with that generator, and the views metadata records it
