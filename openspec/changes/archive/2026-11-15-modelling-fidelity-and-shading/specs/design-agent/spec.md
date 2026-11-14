## ADDED Requirements

### Requirement: Agent compares its build with the views
While iterating on a part program, the agent SHALL look at its build's comparison images for the views whose
whole-object score is below the stop threshold. It SHALL use the dedicated image tool to do so, and use what it sees
to choose the next change. Build reports SHALL give the comparison images as file identifiers, never as image data.

#### Scenario: Seeing the handles
- **WHEN** a cart build's side view scores below the threshold
- **THEN** the agent views the side comparison image, and its next program changes the parts that differ there (for
  example, curving the handles)

#### Scenario: Report stays numeric
- **WHEN** the agent reads a build report
- **THEN** it receives the comparison images' file identifiers and the scores, and no image data

### Requirement: Agent models by techniques
The agent's instructions SHALL tell it to build parts from primitives transformed by modifiers, vertex groups,
cloning, mirroring and booleans, starting from the matching technique note, and to place individual vertices only for
2D profiles and curve control points.

#### Scenario: Wheeled object
- **WHEN** the agent designs an asset with wheels
- **THEN** it searches the notes, and its program builds the wheels from the wheeled-object technique (a rim, a spoke
  cloned around the axle, and mirrored wheels) rather than listing vertex coordinates
