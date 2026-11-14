# knowledge-base Specification

## Purpose
Keeps reusable modelling techniques as global, repo-backed Markdown notes that the agent searches, reads and writes.

## Requirements

### Requirement: Repo-backed global notes
Technique notes SHALL be Markdown files with title, tags and summary front matter in the repository's `knowledge/`
folder. They SHALL be global (shared by all packs) and the repository SHALL ship initial notes. Notes SHALL be grouped in two folders: techniques (how to model
something) and objects (how to approach a concrete object type, referring to techniques). The shipped technique notes
SHALL each give guidance on when to use the technique and a runnable sample, and SHALL cover at least wheeled
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

#### Scenario: Object note found
- **WHEN** the agent searches the notes for "cart"
- **THEN** the cart object note ranks first, naming the techniques it uses and giving a runnable sample

### Requirement: Agent uses and grows the notes
The agent SHALL search the notes before modelling an asset and apply matching ones. It SHALL write or update a note when the user asks for a technique or when it finds one worth reusing. Notes written through the app SHALL be saved in the repository folder.

#### Scenario: Technique recorded
- **WHEN** the user asks the agent to add cracks to wooden parts and the result works
- **THEN** a note about cracks exists in `knowledge/` and a later search for "crack" returns it

#### Scenario: Path outside the folder refused
- **WHEN** a note is written with a slug like `../x`
- **THEN** the write is refused

### Requirement: Notes editable in the UI
The UI SHALL list, search, view, edit, create and delete notes.

#### Scenario: Edit a note
- **WHEN** the user edits a note's body on the Knowledge page and saves
- **THEN** the file in `knowledge/` has the new body and keeps its front matter
