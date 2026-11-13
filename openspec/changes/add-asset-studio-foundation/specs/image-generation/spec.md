# Spec Delta

## Purpose

Produces the 2D material the modelling pipeline needs, using versioned ComfyUI workflows. That material is style anchor images for a pack, style-consistent orthographic turnarounds of single objects, and part masks with their bounds.

## ADDED Requirements

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

### Requirement: Style-referenced object turnaround
The system SHALL generate an object turnaround as one image. The image shows front, side and top orthographic views on a plain background, using the pack's picked anchor image as a style reference. Each view's region in the image SHALL be recorded.

#### Scenario: Cart turnaround
- **WHEN** a turnaround job runs for the asset "wooden cart"
- **THEN** a turnaround image is stored on the asset with front, side and top view regions recorded

### Requirement: Part segmentation
The system SHALL produce, for a given image and a list of part names, one mask per found part per view, with the mask's bounding box and area. Parts that are not found SHALL be reported as missing rather than failing the job.

#### Scenario: Cart parts
- **WHEN** segmentation runs on the cart turnaround with parts "wheel, axle, handle, bed"
- **THEN** masks with bounding boxes are stored for each found part and view, and any part not found is listed as missing

### Requirement: Numeric results for the agent
Image job results offered to the agent SHALL be summarised as identifiers, view regions, mask bounds and areas, so the agent can proceed without viewing pixels.

#### Scenario: Agent reads segmentation
- **WHEN** the agent requests the result of a segmentation job
- **THEN** it receives part names, views, bounding boxes and areas, and no image data unless it explicitly asks to view an image
