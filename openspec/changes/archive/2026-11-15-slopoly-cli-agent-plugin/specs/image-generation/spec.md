# Spec Delta

## MODIFIED Requirements

### Requirement: Workflows as repository files
Each image operation SHALL be defined by a ComfyUI workflow file shipped with the CLI, with named inputs the CLI fills
per job, and SHALL run on the user's configured ComfyUI through its HTTP API. Input and output images SHALL be
transferred through that API, so ComfyUI may run on another machine. Changing or replacing a workflow file SHALL NOT
require code changes as long as its named inputs stay the same.

#### Scenario: Swap a model
- **WHEN** a developer edits the hero workflow to use a different checkpoint, keeping its named inputs
- **THEN** hero jobs use the new checkpoint with no code change

#### Scenario: Remote ComfyUI
- **WHEN** the configured ComfyUI URL points to another machine on the network
- **THEN** a hero job uploads its references there and writes the resulting images into the workspace

### Requirement: Style anchor generation
The system SHALL generate a scene image for a pack from the pack's style guide and a scene description. It SHALL use the pack's picked reference images as style references when present.

#### Scenario: Anchor with references
- **GIVEN** a pack with style text and one picked reference image
- **WHEN** a style anchor job runs with a scene description
- **THEN** one or more scene images are stored in the pack's anchors folder with their metadata
