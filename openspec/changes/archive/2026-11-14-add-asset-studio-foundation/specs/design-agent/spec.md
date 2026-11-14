# Spec Delta

## Purpose

Provides the conversational AI that turns a user's brief into a pack's style guide, concept images and part programs. It runs Claude Code on the user's own subscription and acts on the app only through a defined tool surface.

## ADDED Requirements

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
Starting from a pack with an approved style anchor, the agent SHALL take a "wooden cart" asset to a validated build. That build is mirrored, has a separate rotating axle-and-wheels node, is coloured through role-named main-palette entries, and has silhouette and colour scores recorded.

#### Scenario: Cart run
- **WHEN** the user asks the agent to model the wooden cart and approves its turnaround
- **THEN** the agent stores a manifest and iterates on part programs until a build passes validation or it reports what blocks it, and the final build is viewable in the UI
