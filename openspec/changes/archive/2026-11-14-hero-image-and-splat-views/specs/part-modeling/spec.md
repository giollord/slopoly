## MODIFIED Requirements

### Requirement: Silhouette scoring
Every build SHALL be projected into the orthographic views of the asset's picked hero, in the views' known orientation. For each view it SHALL be scored on the whole-object silhouette, with overlap and signed size errors per axis. For each part and view it SHALL be scored against that part's mask in the same way. The whole-object score is the primary measure of likeness.

#### Scenario: Wheel too small
- **WHEN** the compiled wheel's front-view projection is narrower than its mask
- **THEN** the score for wheel/front reports the overlap and a negative width error

#### Scenario: Object score
- **WHEN** a build's overall proportions match the hero's views but one small part is misplaced
- **THEN** the whole-object scores are high in every view and only that part's scores are low
