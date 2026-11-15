# Spec Delta

## MODIFIED Requirements

### Requirement: Variants of an asset
An asset SHALL have one or more variants, each with a name unique within the asset. Each variant SHALL own its hero
images and their views, its manifest, its program, its builds and its current build. Name, description and triangle
budget SHALL stay on the asset and apply to all of its variants.

#### Scenario: Loaded cart
- **WHEN** the agent adds a variant "loaded" to the cart
- **THEN** the cart has the variants "default" and "loaded", and each has its own folder with its own program and builds

#### Scenario: Shared budget
- **WHEN** the cart's budget is 1500
- **THEN** builds of both cart variants are checked against 1500 triangles

### Requirement: Default variant
Every asset SHALL have a default variant. A new asset SHALL get a variant named "default". Commands that do not name a
variant SHALL act on the default variant. The user and the agent SHALL be able to rename variants and choose which one
is the default.

#### Scenario: Agent omits the variant
- **WHEN** the agent builds the cart without naming a variant
- **THEN** the build is a new build of the cart's default variant

#### Scenario: Existing assets after upgrade
- **WHEN** an asset's `asset.yaml` names no default variant
- **THEN** commands act on its variant named "default", and `slopoly check` reports the asset if it has no such variant

### Requirement: Creating a variant
A new variant SHALL start empty, or copy the manifest and program of another variant of the same asset. Instead, it
can start from a hero image of the asset, which becomes its reference hero.

#### Scenario: Copy and change
- **WHEN** the agent runs `slopoly variant new gnome-village/cart loaded --from default`
- **THEN** "loaded" gets a copy of the default manifest and program, and editing them does not change the default
  variant

#### Scenario: Variant from a hero
- **WHEN** the agent creates a variant from an undecided hero image of the cart
- **THEN** the hero is moved to the new variant and picked as its reference

### Requirement: Versions numbered per variant
Build numbers SHALL count up separately within each variant, starting at 1.

#### Scenario: Independent numbering
- **WHEN** the default cart has builds 1 to 7 and the agent makes the first build of "loaded"
- **THEN** that build is build 1 of "loaded"

### Requirement: Picking a second hero
When the user picks a hero for a variant that already has a reference, the pick window SHALL ask whether to replace
the reference or start a new variant from the hero. Replacing SHALL unpick the old hero, keeping it and its views. A
CLI pick command that does not state the choice SHALL be refused, so no reference is ever replaced silently.

#### Scenario: Replace the reference
- **WHEN** the default cart has reference hero A and the user picks hero C and chooses "Replace reference"
- **THEN** C becomes the reference, A is no longer picked but keeps its views, and later builds compare against C's views

#### Scenario: New variant from the second hero
- **WHEN** the user picks hero C and chooses "New variant" with the name "rustic"
- **THEN** a variant "rustic" is created with C as its reference, and the default variant keeps A

#### Scenario: Choice required
- **WHEN** a CLI pick for a hero of a variant that has a reference does not say whether to replace it
- **THEN** the command fails with an error saying that the variant already has a reference hero and naming the options

### Requirement: Deleting a variant
The user and the agent SHALL be able to delete a variant that is not the asset's only variant with `slopoly rm`. Its
heroes, views, masks, manifest, program and builds SHALL be deleted with it. A variant that scenes use SHALL NOT be
deleted, and the refusal SHALL name those scenes.

#### Scenario: Variant used by a scene
- **WHEN** the agent deletes the "loaded" cart variant while the scene "market square" places it
- **THEN** the deletion is refused with an error naming "market square"
