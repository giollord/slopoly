# design-agent Specification

## Purpose
Provides the conversational AI that turns a user's brief into a pack's style guide, concept images and part programs. It runs Claude Code on the user's own subscription and acts on the app only through a defined tool surface.

## Requirements

### Requirement: Subscription authorisation
The agent SHALL run on the user's Claude subscription, not on API keys. The user SHALL be able to authorise it through their desktop browser. When the credential is missing or rejected, the UI SHALL say so and show how to re-authorise.

#### Scenario: Expired credential
- **WHEN** the agent's credential is rejected during a chat
- **THEN** the chat shows an authorisation error with re-authorisation instructions instead of failing silently

### Requirement: Per-pack chat sessions
Each pack SHALL have a chat with the agent that keeps its conversation across page reloads and app restarts. Agent replies, tool activity and errors SHALL stream into the chat as they happen.

#### Scenario: Resume conversation
- **WHEN** the user restarts the stack and reopens a pack's chat
- **THEN** the earlier messages are shown and the agent continues with that context

#### Scenario: Brief to style
- **WHEN** the user writes "low-poly gnome village in a forest, quirky style, vibrant colours"
- **THEN** the agent writes the pack's style text and a scene description, starts a style anchor job, and the resulting images appear in the pack

### Requirement: App access only through tools
The agent SHALL read and change app state only through the app's tool surface. At minimum the tools SHALL cover:
- reading and updating packs and style guides;
- creating assets;
- starting, reading, cancelling and retrying jobs;
- reading concept image selections and segmentation results;
- storing manifests;
- reading measured part colours and reading and editing the main palette and its variants;
- submitting part programs;
- reading build reports and scores.

#### Scenario: Tool-made changes are visible
- **WHEN** the agent creates an asset through a tool
- **THEN** the asset appears in the UI without a page reload

### Requirement: Token-saving image handling
Tool results SHALL carry identifiers and numbers instead of image data. The agent SHALL view an image only by explicitly requesting it through a dedicated tool.

#### Scenario: Iterating on a build
- **WHEN** the agent reads a build's silhouette scores
- **THEN** it receives per-part numeric scores and no rendered images

### Requirement: Agent respects user selection
The agent SHALL use only concept images the user has not rejected. It SHALL ask the user before proceeding from concepts to modelling.

#### Scenario: Waiting for approval
- **WHEN** turnaround images for an asset are generated
- **THEN** the agent asks the user to pick or reject them before building the manifest

### Requirement: Cart end-to-end
Starting from a pack with an approved style anchor, the agent SHALL take a "wooden cart" asset to a validated build through a picked hero image and its views. That build is mirrored, has a separate rotating axle-and-wheels node, is coloured through role-named main-palette entries, and has whole-object, part and colour scores recorded. The run's outcome, timings and blockers SHALL be recorded.

#### Scenario: Cart run
- **WHEN** the user asks the agent to model the wooden cart and picks one of its hero images
- **THEN** the agent makes the views, segments them, stores a manifest and iterates on part programs until a build passes validation with whole-object scores above the stop threshold, or it reports what blocks it, and the final build is viewable in the UI

### Requirement: Agent compares its build with the views
While iterating on a part program, the agent SHALL look at its build's comparison images for the views whose
whole-object score is below the stop threshold. It SHALL use the dedicated image tool to do so, and use what it sees
to choose the next change. Build reports SHALL give the comparison images as file identifiers, never as image data.

#### Scenario: Seeing the handles
- **WHEN** a cart build's side view scores below the threshold
- **THEN** the agent views the side comparison image, and its next program changes the parts that differ there (for
  example, curving the handles)

#### Scenario: Report stays numeric
- **WHEN** the agent reads a build report
- **THEN** it receives the comparison images' file identifiers and the scores, and no image data

### Requirement: Agent models by techniques
The agent's instructions SHALL tell it to build parts from primitives transformed by modifiers, vertex groups,
cloning, mirroring and booleans, starting from the matching technique note, and to place individual vertices only for
2D profiles and curve control points.

#### Scenario: Wheeled object
- **WHEN** the agent designs an asset with wheels
- **THEN** it searches the notes, and its program builds the wheels from the wheeled-object technique (a rim, a spoke
  cloned around the axle, and mirrored wheels) rather than listing vertex coordinates
