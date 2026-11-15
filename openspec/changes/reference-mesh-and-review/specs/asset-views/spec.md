# Spec Delta

## MODIFIED Requirements

### Requirement: Views rendered from a hero image
For a picked hero the system SHALL build its reference mesh (see reference-mesh) and render separate front, side, top
and back view images from it. The views SHALL use orthographic projection and one shared scale. Each view image SHALL
be stored as a concept of kind view that is linked to its hero, together with the object's exact silhouette mask from
the render.

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
The views job SHALL detect the object's front direction automatically and SHALL check the mesh's handedness. It renders
the mesh from the hero's camera direction and keeps the orientation, mirrored or not, whose render best matches the
hero. The front is the direction the hero image faces, refined by the mirror symmetry of the silhouette. The user SHALL
be able to rerun the views with a corrected front direction.

#### Scenario: Correct the front
- **WHEN** the user turns the front direction by 90 degrees on the hero and remakes the views
- **THEN** new view images replace the old ones, rendered with the corrected front, and the old views and their masks are removed

#### Scenario: Mirrored mesh
- **WHEN** the generated mesh is a mirror image of the object in the hero
- **THEN** the views job mirrors it back, reports `mirrored: true`, and the side view shows the front on the image's
  left as documented

#### Scenario: Front and side agree
- **WHEN** a long X-symmetric object's views are made
- **THEN** the front view shows the object's front and the side view shows the same end on the image's left

## ADDED Requirements

### Requirement: Views framed to the object
Each view SHALL be framed to the object's projected bounds with a margin, so no part of the object is cut off,
whatever its proportions. All views SHALL share one scale in metres per pixel, which the views result reports.

#### Scenario: Long locomotive
- **WHEN** views are made for a locomotive three times longer than it is tall
- **THEN** both ends are inside the side and top views, and a build of the true length scores no size error along
  its length
