## ADDED Requirements

### Requirement: Build comparison on the asset page
The asset page SHALL show, for the selected build, each view's comparison image and object score next to the 3D
viewer, so the user can see where the model differs from the hero's views.

#### Scenario: Compare the cart
- **WHEN** the user opens the cart's asset page after a build against its views
- **THEN** the page shows the front, side, top and back comparisons with their object scores, and selecting an older
  build shows that build's comparisons
