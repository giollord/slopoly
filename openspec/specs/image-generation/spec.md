# image-generation Specification

## Purpose
Produces the 2D material the modelling pipeline needs, using versioned ComfyUI workflows. That material is style anchor images for a pack, style-consistent orthographic turnarounds of single objects, and part masks with their bounds.

## Requirements

### Requirement: Workflows as repository files
Each image operation SHALL be defined by a ComfyUI workflow file in the repository, with named inputs the app fills per job. Changing or replacing a workflow file SHALL NOT require application code changes as long as its named inputs stay the same.

#### Scenario: Swap a model
- **WHEN** a developer edits the turnaround workflow to use a different checkpoint, keeping its named inputs
- **THEN** turnaround jobs use the new checkpoint with no code change

### Requirement: Style anchor generation
The system SHALL generate a scene image for a pack from the pack's style guide and a scene description. It SHALL use the pack's picked reference images as style references when present.

#### Scenario: Anchor with references
- **GIVEN** a pack with style text and one picked reference image
- **WHEN** a style anchor job runs with a scene description
- **THEN** one or more scene images are stored as concept images of the pack

### Requirement: Part segmentation
The system SHALL produce, for the view images of a hero and a list of part names, one mask per found part per view, with the mask's bounding box and area. The whole-object mask of each view SHALL come from the view's render silhouette. Parts that are not found SHALL be reported as missing rather than failing the job.

#### Scenario: Cart parts
- **WHEN** segmentation runs on the cart hero's views with parts "wheel, axle, handle, bed"
- **THEN** masks with bounding boxes are stored for each found part and view, and any part not found is listed as missing

### Requirement: Numeric results for the agent
Image job results offered to the agent SHALL be summarised as identifiers, view names, image sizes, silhouette bounds, mask bounds and areas, so the agent can proceed without viewing pixels.

#### Scenario: Agent reads segmentation
- **WHEN** the agent requests the result of a segmentation job
- **THEN** it receives part names, views, bounding boxes and areas, and no image data unless it explicitly asks to view an image

### Requirement: Style-referenced hero image
The system SHALL generate hero images of one asset: a single three-quarter front view of the whole object, alone on a plain light background, using up to three of the pack's picked style anchors as style references. A job SHALL produce the requested number of images (1 to 4), each with its seed recorded.

#### Scenario: Cart heroes
- **WHEN** a hero job runs for the asset "wooden cart" with count 2
- **THEN** two hero images of the cart are stored on the asset, undecided, each with its seed

#### Scenario: No picked anchor
- **WHEN** a hero job is requested for an asset of a pack without a picked style anchor
- **THEN** the request is refused with an error asking to pick a style anchor first

### Requirement: Image model chosen by comparison
The default model for style anchors and heroes SHALL be chosen by a recorded comparison of the candidate local models on the same prompts and references. The comparison covers style match, object correctness and element placement.

#### Scenario: Recorded choice
- **WHEN** the comparison is complete
- **THEN** the chosen model, the rejected candidates and the reasons are recorded in the change notes, and the workflow files use the chosen model
