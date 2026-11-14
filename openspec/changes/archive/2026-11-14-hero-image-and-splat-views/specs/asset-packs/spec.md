## MODIFIED Requirements

### Requirement: Concept images with selection
Generated images SHALL be stored as concept images linked to their pack or asset and their originating job. Their kind is style anchor, hero or view, and a view SHALL be linked to the hero it was rendered from. The user SHALL be able to mark anchors and heroes picked or rejected. Only picked images SHALL be used as references for later steps, and the views of a hero are usable while the hero is picked.

#### Scenario: Reject an image
- **WHEN** the user rejects a hero image of the cart
- **THEN** it is hidden from the default gallery view and no longer offered to the agent as a reference

#### Scenario: Regenerate on request
- **WHEN** the user asks for more variants of a concept
- **THEN** new images are added alongside the existing ones and are neither picked nor rejected

#### Scenario: Deleting a hero removes its views
- **WHEN** the user deletes a hero that has views
- **THEN** its views and their masks are deleted with it
