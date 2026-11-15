# Spec Delta

## MODIFIED Requirements

### Requirement: Scenes place built assets
A pack SHALL hold named scenes, each a file in the pack's `scenes/` folder. Each scene lists placements of the pack's
assets with a name, an optional variant (the asset's default variant when omitted), position, rotation and scale.
`slopoly scene build` SHALL build a scene from, for each placement, the build chosen for its asset and variant.

#### Scenario: Agent assembles a scene
- **WHEN** the agent writes a scene "market square" placing the cart twice and a well once and builds it
- **THEN** the scene build produces one combined model with three placements

#### Scenario: Unbuilt asset refused
- **WHEN** a scene places an asset that has no build
- **THEN** the scene build fails with an error that names the asset

#### Scenario: Two cart variants
- **WHEN** a scene places one default cart and one loaded cart
- **THEN** the combined model shows each cart in its own variant

### Requirement: Scenes editable by the user
The user and the agent SHALL be able to edit a scene's placements (add, remove, change numbers and variant) in its
file, rebuild it with `slopoly scene build` and look at it with `slopoly view`.

#### Scenario: Move a placement
- **WHEN** the user changes the cart's x position in the scene file and rebuilds it
- **THEN** the scene model shows the cart moved

#### Scenario: Refresh after a new build
- **WHEN** the cart gets a new current build and the user rebuilds an unchanged scene
- **THEN** the scene shows the new cart

### Requirement: Versions chosen per asset and variant
A scene SHALL choose, for each asset and variant it uses, one build that applies to all of its placements at once:
"current" (the default) or a build number. `slopoly scene build --current` SHALL set every choice back to current.

#### Scenario: Older carts everywhere
- **WHEN** the scene places the cart five times, sets the cart's build to 4 and is built
- **THEN** all five carts use build 4, whatever the cart's current build is

#### Scenario: Back to current
- **WHEN** the agent runs `slopoly scene build gnome-village/scenes/market-square --current`
- **THEN** every choice in the scene file is current and every placement uses its variant's current build

#### Scenario: Version without a build
- **WHEN** the chosen build of an asset has no model
- **THEN** the scene build fails with an error that names the asset, the variant and the build number

## REMOVED Requirements

### Requirement: Scene chat
**Reason**: The scene page and its chat are removed.
**Migration**: Ask your agent about the scene by naming it. It edits the scene file and rebuilds.
