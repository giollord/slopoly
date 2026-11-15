## ADDED Requirements

### Requirement: Versions chosen per asset and variant
A scene SHALL let the user choose, for each asset and variant it uses, one program version that applies to all of its
placements at once: "current" (the default) or a numbered version. The page SHALL also offer an action that sets every
choice back to current.

#### Scenario: Older carts everywhere
- **WHEN** the scene places the cart five times and the user sets the cart's version to v4 and saves
- **THEN** all five carts are built from v4's latest build, whatever the cart's current version is

#### Scenario: Back to current
- **WHEN** the user uses "use current everywhere" and saves
- **THEN** every placement is built from its variant's current version

#### Scenario: Version without a build
- **WHEN** the chosen version of an asset has no build with a model
- **THEN** saving fails with an error that names the asset, the variant and the version

### Requirement: Scene chat
The scene page SHALL embed a chat with the agent next to the scene model. The chat's context names the scene and its
placed assets with their variants and chosen versions.

#### Scenario: Ask for a layout change
- **WHEN** the user writes "move the well to the middle of the square" in the scene page's chat
- **THEN** the agent knows which scene is meant, saves the scene with the well moved, and the page shows the rebuilt
  scene

## MODIFIED Requirements

### Requirement: Scenes place built assets
A pack SHALL hold named scenes. Each scene lists placements of the pack's assets with a name, an optional variant (the asset's default variant when omitted), position, rotation and scale. Saving a scene SHALL queue a scene build that uses, for each placement, the latest build of the version chosen for its asset and variant.

#### Scenario: Agent assembles a scene
- **WHEN** the agent saves a scene "market square" placing the cart twice and a well once
- **THEN** a scene build runs and the scene shows one combined model with three placements

#### Scenario: Unbuilt asset refused
- **WHEN** a scene places an asset that has no build
- **THEN** saving fails with an error that names the asset

#### Scenario: Two cart variants
- **WHEN** a scene places one default cart and one loaded cart
- **THEN** the combined model shows each cart in its own variant

### Requirement: Scenes editable by the user
The user SHALL be able to view a scene's model, edit its placements (add, remove, change numbers and variant) and rebuild it. The save action SHALL always be enabled: with unsaved edits it reads "Save and build"; without them it reads "Refresh" and rebuilds the scene from the chosen versions.

#### Scenario: Move a placement
- **WHEN** the user changes the cart's x position and saves
- **THEN** the scene is rebuilt with the cart moved

#### Scenario: Refresh after a new build
- **WHEN** the cart gets a new current version and the user clicks "Refresh" on an unchanged scene
- **THEN** the scene is rebuilt and shows the new cart
