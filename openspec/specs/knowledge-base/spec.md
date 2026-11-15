# knowledge-base Specification

## Purpose
Keeps reusable modelling techniques as global, repo-backed Markdown notes that the agent searches, reads and writes.

## Requirements

### Requirement: Repo-backed global notes
Technique notes SHALL be Markdown files with title, tags and summary front matter. Shipped notes SHALL be reference
files of the `slopoly` skill and global (shared by all packs and workspaces). Notes SHALL be grouped in two folders:
techniques (how to model something) and objects (how to approach a concrete object type, referring to techniques).
The shipped technique notes SHALL each give guidance on when to use the technique and a runnable sample, and SHALL
cover at least wheeled objects, surface texture from meshes, organic deformation, holes and openings, curved and bent
parts, and repeats (cloning and mirroring). Every code example in the shipped notes SHALL build without errors.

#### Scenario: Shipped notes available
- **WHEN** the plugin is installed in an agent
- **THEN** the skill points the agent to the shipped notes, and the agent can list and search them

#### Scenario: Wheel technique found
- **WHEN** the agent searches the notes for "spoked wheel"
- **THEN** a note with a runnable spoked-wheel example is found

#### Scenario: Organic technique found
- **WHEN** the agent searches the notes for "branch" or "organic"
- **THEN** the organic deformation note is found, with a sample that bends and tapers a box using a vertex group

#### Scenario: Object note found
- **WHEN** the agent searches the notes for "cart"
- **THEN** the cart object note is found, naming the techniques it uses and giving a runnable sample

### Requirement: Agent uses and grows the notes
The agent SHALL search the shipped notes and the workspace's notes before modelling an asset and apply matching ones.
It SHALL write or update a note in the workspace's `knowledge/` folder when the user asks for a technique or when it
finds one worth reusing. `slopoly check` SHALL validate the workspace notes' front matter.

#### Scenario: Technique recorded
- **WHEN** the user asks the agent to add cracks to wooden parts and the result works
- **THEN** a note about cracks exists in the workspace's `knowledge/` folder and a later search for "crack" finds it

#### Scenario: Path outside the folder refused
- **WHEN** a note file in the workspace's `knowledge/` folder has a name that is not a kebab-case slug, or lies outside
  its techniques and objects folders
- **THEN** `slopoly check` reports the file

#### Scenario: Invalid note
- **WHEN** a workspace note has no title in its front matter
- **THEN** `slopoly check` reports the note's file and the missing field
