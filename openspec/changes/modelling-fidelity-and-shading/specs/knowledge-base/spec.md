## MODIFIED Requirements

### Requirement: Repo-backed global notes
Technique notes SHALL be Markdown files with title, tags and summary front matter in the repository's `knowledge/`
folder. They SHALL be global (shared by all packs) and the repository SHALL ship initial notes. The shipped notes SHALL
include modelling rulesets, one per technique, each with guidance on when to use it and a runnable sample: wheeled
objects, surface texture from meshes, organic deformation, holes and openings, curved and bent parts, and repeats
(cloning and mirroring). Every code example in the shipped notes SHALL build without errors.

#### Scenario: Shipped notes available
- **WHEN** the app starts on a fresh clone
- **THEN** the notes from the repository's `knowledge/` folder are listed and searchable

#### Scenario: Wheel technique found
- **WHEN** the agent searches the notes for "spoked wheel"
- **THEN** a note with a runnable spoked-wheel example is returned

#### Scenario: Organic technique found
- **WHEN** the agent searches the notes for "branch" or "organic"
- **THEN** the organic deformation note is returned, with a sample that bends and tapers a box using a vertex group
