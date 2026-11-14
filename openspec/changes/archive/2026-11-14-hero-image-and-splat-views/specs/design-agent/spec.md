## MODIFIED Requirements

### Requirement: Cart end-to-end
Starting from a pack with an approved style anchor, the agent SHALL take a "wooden cart" asset to a validated build through a picked hero image and its views. That build is mirrored, has a separate rotating axle-and-wheels node, is coloured through role-named main-palette entries, and has whole-object, part and colour scores recorded. The run's outcome, timings and blockers SHALL be recorded.

#### Scenario: Cart run
- **WHEN** the user asks the agent to model the wooden cart and picks one of its hero images
- **THEN** the agent makes the views, segments them, stores a manifest and iterates on part programs until a build passes validation with whole-object scores above the stop threshold, or it reports what blocks it, and the final build is viewable in the UI
