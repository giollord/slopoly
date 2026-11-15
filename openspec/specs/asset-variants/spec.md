# asset-variants Specification

## Purpose
Lets one asset have several looks. Each variant has its own reference hero and views, manifest, program versions,
builds and current version, while the asset keeps its name, description and triangle budget.

## Requirements

### Requirement: Variants of an asset
An asset SHALL have one or more variants, each with a name unique within the asset. Each variant SHALL own its hero
images and their views, its manifest, its program versions, its builds and its current version. Name, description and
triangle budget SHALL stay on the asset and apply to all of its variants.

#### Scenario: Loaded cart
- **WHEN** the user adds a variant "loaded" to the cart
- **THEN** the cart has the variants "default" and "loaded", and each one shows its own builds and program versions

#### Scenario: Shared budget
- **WHEN** the cart's budget is 1500
- **THEN** builds of both cart variants are checked against 1500 triangles

### Requirement: Default variant
Every asset SHALL have a default variant. A new asset SHALL get a variant named "default". Operations that do not name
a variant, from the UI, the API or the agent, SHALL act on the default variant. The user SHALL be able to rename
variants and choose which one is the default.

#### Scenario: Agent omits the variant
- **WHEN** the agent submits a part program for the cart without naming a variant
- **THEN** the program becomes a new version of the cart's default variant

#### Scenario: Existing assets after upgrade
- **WHEN** the app starts on data created before variants existed
- **THEN** each asset has one variant called "default" that holds all of the asset's earlier heroes, views, manifest,
  program versions, builds and current version

### Requirement: Creating a variant
A new variant SHALL start empty, or copy the manifest and current program of another variant of the same asset as its
first version. Instead, it can start from a hero image of the asset, which becomes its reference hero.

#### Scenario: Copy and change
- **WHEN** the user creates the variant "loaded" from "default"
- **THEN** "loaded" gets a copy of the default manifest and its current program as version 1, and editing them does
  not change the default variant

#### Scenario: Variant from a hero
- **WHEN** the user creates a variant from an undecided hero image of the cart
- **THEN** the hero is moved to the new variant and picked as its reference

### Requirement: Versions numbered per variant
Program version numbers SHALL count up separately within each variant, starting at 1.

#### Scenario: Independent numbering
- **WHEN** the default cart has versions 1 to 7 and the user submits the first program of "loaded"
- **THEN** that program is version 1 of "loaded"

### Requirement: One reference hero per variant
A variant SHALL have at most one picked hero, its reference. Builds of a variant SHALL compare only against the views
of that variant's reference hero. A build of a variant without a reference hero SHALL skip the view comparison and
say so in its report.

#### Scenario: Builds use their own reference
- **WHEN** "default" has reference hero A with views and "loaded" has reference hero B with views
- **THEN** default builds are scored against A's views and loaded builds against B's views

#### Scenario: No reference
- **WHEN** a variant without a picked hero is built
- **THEN** the build succeeds and its report says the comparison was skipped because the variant has no reference hero

### Requirement: Picking a second hero
When the user picks a hero for a variant that already has a reference, the system SHALL ask whether to replace the
reference or start a new variant from the hero. Replacing SHALL unpick the old hero, keeping it and its views. A pick
request that does not state the choice SHALL be refused, so no reference is ever replaced silently.

#### Scenario: Replace the reference
- **WHEN** the default cart has reference hero A and the user picks hero C and chooses "Replace reference"
- **THEN** C becomes the reference, A is no longer picked but keeps its views, and later builds compare against C's views

#### Scenario: New variant from the second hero
- **WHEN** the user picks hero C and chooses "New variant" with the name "rustic"
- **THEN** a variant "rustic" is created with C as its reference, and the default variant keeps A

#### Scenario: Choice required
- **WHEN** a pick request for a hero of a variant that has a reference does not say whether to replace it
- **THEN** the request fails with an error saying that the variant already has a reference hero and naming the options

### Requirement: Deleting a variant
The user SHALL be able to delete a variant that is not the asset's only variant. Its heroes, views, masks, manifest,
program versions and builds SHALL be deleted with it. A variant that scenes use SHALL NOT be deleted, and the refusal
SHALL name those scenes.

#### Scenario: Variant used by a scene
- **WHEN** the user deletes the "loaded" cart variant while the scene "market square" places it
- **THEN** the deletion is refused with an error naming "market square"

### Requirement: Asset status from its variants
Each variant SHALL have a status (concept, manifest, built or validated), and the asset's status SHALL be the furthest
status among its variants.

#### Scenario: One validated variant
- **WHEN** the default cart is validated and the loaded cart only has a manifest
- **THEN** the cart is listed as validated, and the asset page shows each variant's own status
