# design-agent Specification

## Purpose
Provides the conversational AI that turns a user's brief into a pack's style guide, concept images and part programs. It runs Claude Code on the user's own subscription and acts on the app only through a defined tool surface.

## Requirements

### Requirement: Subscription authorisation
The agent SHALL run on the user's Claude subscription, not on API keys. The user SHALL be able to authorise it through their desktop browser. When the credential is missing or rejected, the UI SHALL say so and show how to re-authorise.

#### Scenario: Expired credential
- **WHEN** the agent's credential is rejected during a chat
- **THEN** the chat shows an authorisation error with re-authorisation instructions instead of failing silently

### Requirement: App access only through tools
The agent SHALL read and change app state only through the app's tool surface. At minimum the tools SHALL cover:
- reading and updating packs and style guides;
- creating assets and managing their variants;
- starting, reading, cancelling and retrying jobs;
- reading concept image selections and segmentation results;
- storing manifests;
- reading measured part colours, and reading and editing palettes;
- submitting part programs;
- reading build reports and scores.

#### Scenario: Tool-made changes are visible
- **WHEN** the agent creates an asset through a tool
- **THEN** the asset appears in the UI without a page reload

#### Scenario: Variant omitted
- **WHEN** the agent calls a manifest, program, build or hero tool for the cart without naming a variant
- **THEN** the tool acts on the cart's default variant

#### Scenario: Program for a named variant
- **WHEN** the agent submits a program for the cart with variant "loaded"
- **THEN** it becomes the next version of the loaded variant and the default variant is unchanged

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

### Requirement: Multiple chats
The user SHALL be able to start a new chat with the agent at any time from any page, and to reopen earlier chats from
a list, newest first. Each chat SHALL keep its own conversation and agent session across page reloads and app restarts.
Agent replies, tool activity and errors SHALL stream into the chat as they happen.

#### Scenario: Start fresh
- **WHEN** the user clicks "New chat" while an earlier chat is open
- **THEN** an empty chat opens, and the next message starts a new agent session without the earlier conversation

#### Scenario: Resume conversation
- **WHEN** the user restarts the stack and reopens an earlier chat from the list
- **THEN** its messages are shown and the agent continues with that chat's context

#### Scenario: Brief to style
- **WHEN** the user writes "low-poly gnome village in a forest, quirky style, vibrant colours" in a chat started on the
  pack page
- **THEN** the agent writes the pack's style text and a scene description, starts a style anchor job, and the resulting
  images appear in the pack

### Requirement: Chat page context
A new chat SHALL record the page it was started on and the objects shown there: pack, asset, variant, selected build,
scene or concept. The first message sent to the agent SHALL include a context block that names each of these objects
with its id and key state.

#### Scenario: Chat from the asset page
- **WHEN** the user starts a chat on the cart's asset page, with variant "loaded" and build 12 selected, and writes
  "the wheels are too thick"
- **THEN** the agent's first prompt names the pack, the cart asset, the "loaded" variant and build 12 with their ids
  and the build's program version, so the agent can read that build's report without asking which asset is meant

#### Scenario: Chat outside a pack
- **WHEN** the user starts a chat on the knowledge page
- **THEN** the chat belongs to no pack, and its context block says that the user is on the knowledge page

### Requirement: Current page with each message
Every later message in a chat SHALL carry a one-line note of the page the user is on when sending it, with the ids of
that page's objects.

#### Scenario: Moving to another asset
- **WHEN** the user continues a chat started on the cart page after opening the well's asset page
- **THEN** the agent receives the message with a note that the user is now looking at the well and its selected build

### Requirement: Stop the agent
While an agent turn of a chat is queued or running, the chat SHALL show a Stop control. Stopping SHALL cancel the
running turn and any queued turns of that chat, and the agent SHALL stop calling tools. The chat SHALL keep what was
said and done up to the stop, and the next message SHALL continue the same session.

#### Scenario: Stop a long turn
- **WHEN** the agent is iterating on part programs and the user clicks Stop
- **THEN** the turn ends as cancelled within a few seconds, no further tool calls appear, and the chat shows that it
  was stopped

#### Scenario: Continue after stopping
- **WHEN** the user sends "only fix the handles" after stopping a turn
- **THEN** the agent continues the same conversation and knows what it was doing before the stop

### Requirement: Chats on the asset and scene pages
The asset page and the scene page SHALL embed a chat next to the model. The embedded chat SHALL open the newest chat
started on that asset, or on that scene, and SHALL offer "New chat" and the chat list. The same chat SHALL also be
reachable from the chat drawer on every page.

#### Scenario: Back to the asset's chat
- **WHEN** the user returns to the cart's asset page after chatting there yesterday
- **THEN** the embedded chat shows yesterday's chat about the cart
