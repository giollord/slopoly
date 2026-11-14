# Spec Delta

## Purpose

Assembles built assets of a pack into scenes: placements with transforms, combined into one model with a placement report.

## ADDED Requirements

### Requirement: Scenes place built assets
A pack SHALL hold named scenes. Each scene lists placements of the pack's assets with a name, position, rotation and scale. Saving a scene SHALL queue a scene build that uses each placed asset's latest build of its current program version.

#### Scenario: Agent assembles a scene
- **WHEN** the agent saves a scene "market square" placing the cart twice and a well once
- **THEN** a scene build runs and the scene shows one combined model with three placements

#### Scenario: Unbuilt asset refused
- **WHEN** a scene places an asset that has no build
- **THEN** saving fails with an error that names the asset

### Requirement: Scene report
A scene build SHALL report each placement's world bounds and whether it is grounded, and list placement pairs whose bounding boxes overlap by more than 10 % of the smaller one.

#### Scenario: Overlap reported
- **WHEN** two placements are put at the same position
- **THEN** the report lists them as an overlapping pair

### Requirement: Scenes editable by the user
The user SHALL be able to view a scene's model, edit its placements (add, remove, change numbers) and rebuild it.

#### Scenario: Move a placement
- **WHEN** the user changes the cart's x position and saves
- **THEN** the scene is rebuilt with the cart moved
