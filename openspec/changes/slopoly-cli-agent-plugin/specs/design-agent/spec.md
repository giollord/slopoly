# Spec Delta

## ADDED Requirements

### Requirement: Any supported agent
The design agent SHALL be whichever coding agent the user runs with the `slopoly` skill (see agent-plugin). Slopoly
SHALL NOT run an agent itself, embed an agent SDK or need an agent subscription credential.

#### Scenario: No credential
- **WHEN** Slopoly is installed and used through the user's agent
- **THEN** no agent token or subscription setting exists in Slopoly's configuration

### Requirement: App access through the CLI and workspace files
The agent SHALL change workspace state only through `slopoly` commands and by editing the files the skill names as
agent-editable: `style.md`, `manifest.yaml`, `program.py`, scene files and knowledge notes. The CLI SHALL cover:
- creating packs, assets, variants and scenes;
- starting, waiting on, cancelling and retrying jobs;
- reading selections, segmentation results and measured colours;
- editing palettes;
- building, viewing and exporting;
- reading build reports and scores.

#### Scenario: Agent edits the program
- **WHEN** the agent changes the cart's `program.py` and runs `slopoly build gnome-village/cart`
- **THEN** a new build of the default variant is made from the edited program

#### Scenario: Program for a named variant
- **WHEN** the agent edits the loaded variant's `program.py` and builds `gnome-village/cart:loaded`
- **THEN** the new build belongs to the loaded variant and the default variant is unchanged

## MODIFIED Requirements

### Requirement: Token-saving image handling
CLI results SHALL carry file paths and numbers instead of image data. The agent SHALL view an image only by opening its
file on purpose.

#### Scenario: Iterating on a build
- **WHEN** the agent reads a build's silhouette scores
- **THEN** it receives per-part numeric scores and image paths, and no image data

### Requirement: Agent respects user selection
The agent SHALL use only concept images the user has not rejected. It SHALL ask the user, through the pick window,
before proceeding from concepts to modelling.

#### Scenario: Waiting for approval
- **WHEN** hero images for an asset are generated
- **THEN** the agent opens a pick window for them and waits on its job before making views or a manifest

### Requirement: Cart end-to-end
Starting from a pack with an approved style anchor, the agent SHALL take a "wooden cart" asset to a validated build through a picked hero image and its views. That build is mirrored, has a separate rotating axle-and-wheels node, is coloured through role-named main-palette entries, and has whole-object, part and colour scores recorded. The run's outcome, timings and blockers SHALL be recorded.

#### Scenario: Cart run
- **WHEN** the user asks their agent to model the wooden cart and picks one of its hero images in the pick window
- **THEN** the agent makes the views, segments them, writes a manifest and iterates on the part program until a build
  passes validation with whole-object scores above the stop threshold, or it reports what blocks it, and the final
  build opens in the view window

### Requirement: Agent compares its build with the views
While iterating on a part program, the agent SHALL look at its build's comparison images for the views whose
whole-object score is below the stop threshold, by opening those image files, and use what it sees to choose the next
change. Build results SHALL give the comparison images as file paths, never as image data.

#### Scenario: Seeing the handles
- **WHEN** a cart build's side view scores below the threshold
- **THEN** the agent opens the side comparison image, and its next program changes the parts that differ there (for
  example, curving the handles)

#### Scenario: Report stays numeric
- **WHEN** the agent reads a build result
- **THEN** it receives the comparison images' paths and the scores, and no image data

## REMOVED Requirements

### Requirement: Subscription authorisation
**Reason**: Slopoly no longer runs an agent. The user's own agent handles its own authorisation.
**Migration**: Install the plugin in your agent (see agent-plugin).

### Requirement: App access only through tools
**Reason**: The HTTP API and MCP tool surface are removed.
**Migration**: See "App access through the CLI and workspace files".

### Requirement: Multiple chats
**Reason**: Chats are the user's agent's sessions, not part of Slopoly.
**Migration**: Use your agent's own sessions. `slopoly status` lets a new session pick up the workspace state.

### Requirement: Chat page context
**Reason**: There are no studio pages to take context from.
**Migration**: Name the target (`<pack>/<asset>:<variant>`) in your request, or let the agent use `slopoly status`.

### Requirement: Current page with each message
**Reason**: There are no studio pages.
**Migration**: None.

### Requirement: Stop the agent
**Reason**: Stopping an agent turn is the agent's own feature.
**Migration**: Use your agent's stop control. Running jobs can be cancelled with `slopoly cancel`.

### Requirement: Chats on the asset and scene pages
**Reason**: The asset and scene pages are removed.
**Migration**: None.
