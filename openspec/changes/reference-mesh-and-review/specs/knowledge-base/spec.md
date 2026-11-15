# Spec Delta

## MODIFIED Requirements

### Requirement: Repo-backed global notes
Technique notes SHALL be Markdown files with title, tags and summary front matter. Shipped notes SHALL be reference
files of the `slopoly` skill and global (shared by all packs and workspaces). Notes SHALL be grouped in two folders:
techniques (how to model something) and objects (how to approach a concrete object type, referring to techniques).
The shipped technique notes SHALL each give guidance on when to use the technique and a runnable sample. They SHALL
cover at least:
- wheeled objects, surface texture from meshes, organic deformation, holes and openings, curved and bent parts, and
  repeats (cloning and mirroring);
- bands and trims as profile steps with paint, curved sheets made from a curve with a wide profile, tapered and bent
  horns and spikes, and safe jitter on thin walls.

The shipped object notes SHALL cover at least a cart, a steam locomotive and bone decorations. The triangle budget
note SHALL give a range for hero vehicles and machines. Every code example in the shipped notes SHALL build without
errors.

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

#### Scenario: Horn technique found
- **WHEN** the agent searches the notes for "horn", "spike" or "tusk"
- **THEN** a note with a runnable sample of a tapered, bent horn is found

#### Scenario: Locomotive note found
- **WHEN** the agent searches the notes for "locomotive"
- **THEN** the steam locomotive object note is found, covering the cowcatcher's V plan, the stack's lathe profile,
  the cab and the frame between the wheels, with a runnable sample
