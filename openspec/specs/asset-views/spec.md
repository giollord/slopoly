# asset-views Specification

## Purpose
TBD - created by archiving change hero-image-and-splat-views. Update Purpose after archive.

## Requirements

### Requirement: Views rendered from a hero image
For a picked hero image the system SHALL build a 3D Gaussian splat locally and render separate front, side, top and back view images from it. The views SHALL use orthographic projection and one shared scale. Each view image SHALL be stored as a concept of kind view that is linked to its hero, together with the object's exact silhouette mask from the render.

#### Scenario: Cart views
- **WHEN** a views job runs for the picked cart hero
- **THEN** four view images (front, side, top, back) and their silhouette masks are stored, linked to the hero

#### Scenario: Consistent proportions
- **WHEN** the views of one hero are measured
- **THEN** the object's width in the front view equals its width in the top view, and its depth in the side view equals its depth in the top view, within 2 %

#### Scenario: Hero not picked
- **WHEN** a views job is requested for a hero that is not picked
- **THEN** the request is refused with an error that says the hero must be picked first

### Requirement: Front direction
The views job SHALL detect the object's front direction automatically, as the horizontal direction whose rendered silhouette is most nearly mirror-symmetric, preferring the direction the hero image faces. The user SHALL be able to rerun the views with a corrected front direction.

#### Scenario: Correct the front
- **WHEN** the user turns the front direction by 90 degrees on the hero and remakes the views
- **THEN** new view images replace the old ones, rendered with the corrected front, and the old views and their masks are removed

### Requirement: Only local, commercially usable models
Hero, view and segmentation generation SHALL run only on models executed on the user's machine whose licences allow commercial use of the outputs. No paid or remote service SHALL be called.

#### Scenario: No network generation
- **WHEN** hero and views jobs run with the network to external services blocked
- **THEN** they complete normally
