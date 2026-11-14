# knowledge-base Specification

## Purpose
Keeps reusable modelling techniques as global, repo-backed Markdown notes that the agent searches, reads and writes.

## Requirements

### Requirement: Repo-backed global notes
Technique notes SHALL be Markdown files with title, tags and summary front matter in the repository's `knowledge/` folder. They SHALL be global (shared by all packs) and the repository SHALL ship initial notes.

#### Scenario: Shipped notes available
- **WHEN** the app starts on a fresh clone
- **THEN** the notes from the repository's `knowledge/` folder are listed and searchable

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
