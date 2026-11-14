# Spec Delta

## Purpose

Extends packs and assets with per-asset triangle budgets, concept deletion and concept revisions.

## ADDED Requirements

### Requirement: Per-asset triangle budget
An asset MAY have its own triangle budget. Builds SHALL use the asset's budget when it is set and the pack's budget otherwise.

#### Scenario: Character with a larger budget
- **WHEN** the pack budget is 2000 and the "gnome" asset has budget 3500
- **THEN** a 3000-triangle gnome build passes the budget check and a 3000-triangle cart build does not

### Requirement: Concept revision on request
On request the agent SHALL generate new images from a concept's generation with a fresh seed and a user-chosen count, optionally applying a described change with the concept itself as the first reference. New images SHALL start neither picked nor rejected. Each concept SHALL record the seed it was generated with.

#### Scenario: Changed variants
- **WHEN** the agent revises a concept with change "add a red roof" and count 2
- **THEN** two new undecided images appear, generated with the concept as first reference and the change in the prompt

### Requirement: Concept deletion
The user SHALL be able to delete a concept image; its part masks are removed with it.

#### Scenario: Delete a turnaround
- **WHEN** the user deletes a segmented turnaround
- **THEN** the image and its masks no longer appear for the user or the agent
