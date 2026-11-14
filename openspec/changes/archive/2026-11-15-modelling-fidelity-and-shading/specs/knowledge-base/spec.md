## MODIFIED Requirements

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
