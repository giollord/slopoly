# asset-variants Specification

## Purpose
Lets one asset have several looks. Each variant has its own reference hero and views, manifest, program versions,
builds and current version, while the asset keeps its name, description and triangle budget.

## Requirements

### Requirement: Variants of an asset
An asset SHALL have one or more variants, each with a name unique within the asset. Hero images, with their views and
masks, SHALL belong to the asset; each variant SHALL name one of them as its reference hero, and own its manifest, its
program, its builds and its current build. Name, description and triangle budget SHALL stay on the asset and apply to
all of its variants.

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
- **THEN** the hero stays in the cart's `heroes/` folder, is marked picked and becomes the new variant's reference

### Requirement: Versions numbered per variant
Build numbers SHALL count up separately within each variant, starting at 1. A build that fails with a program error
SHALL be moved to the variant's `builds/rejected/` folder, and its number SHALL NOT be used again.

#### Scenario: Independent numbering
- **WHEN** the default cart has builds 1 to 7 and the agent makes the first build of "loaded"
- **THEN** that build is build 1 of "loaded"

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
Each hero the user picks SHALL become the reference of the variant named for it: a new variant when the name is
new, or the named existing variant, whose old reference is then rejected (moved with its views and masks to the
`rejected/` folders) unless another variant still uses it. The non-interactive `slopoly pick --set <hero> --state
picked` SHALL take the variant with `--variant <name>`, defaulting to the asset's default variant.

#### Scenario: Replace the reference
- **WHEN** the default cart has reference hero A and the user picks hero C for the variant "default"
- **THEN** C becomes the reference, A is moved to `heroes/rejected/` with its views, and later builds compare against
  C's views

#### Scenario: New variant from the second hero
- **WHEN** the user picks hero C and names its variant "rustic"
- **THEN** a variant "rustic" is created with C as its reference, and the default variant keeps A

#### Scenario: Choice required
- **WHEN** the user picks a hero and clears its variant name
- **THEN** confirming is refused with an error asking for the variant name, and nothing changes

### Requirement: Deleting a variant
The user and the agent SHALL be able to delete a variant that is not the asset's only variant with `slopoly rm`. Its
manifest, program and builds SHALL be deleted with it; the asset's heroes stay. A variant that scenes use SHALL NOT be
deleted, and the refusal SHALL name those scenes.

#### Scenario: Variant used by a scene
- **WHEN** the agent deletes the "loaded" cart variant while the scene "market square" places it
- **THEN** the deletion is refused with an error naming "market square"

### Requirement: Asset status from its variants
Each variant SHALL have a status (concept, manifest, built or validated), and the asset's status SHALL be the furthest
status among its variants.

#### Scenario: One validated variant
- **WHEN** the default cart is validated and the loaded cart only has a manifest
- **THEN** the cart is listed as validated, and the asset page shows each variant's own status

### Requirement: Replacing a variant's reference
`slopoly variant reference <pack>/<asset>:<variant> <hero>` SHALL make a hero of the asset the variant's reference,
keeping its manifest, program and builds. The old reference SHALL be rejected as when a pick replaces it. A hero pick
started with `--for <variant>` SHALL suggest that variant's name for the picked hero, so confirming replaces its
reference rather than creating a new variant.

#### Scenario: Revise then replace
- **WHEN** the default locomotive has reference hero 3 and builds 1 to 9, and the agent runs `slopoly gen revise`
  on hero 3, then `slopoly pick orcish/locomotive --heroes --for default`, and the user picks hero 6
- **THEN** hero 6 becomes the default variant's reference, builds 1 to 9 and the program stay, hero 3 is rejected,
  and no new variant is created

#### Scenario: Command
- **WHEN** the agent runs `slopoly variant reference orcish/locomotive:default heroes/hero_006.png`
- **THEN** hero 6 becomes the default variant's reference, and the variant keeps its program and builds
