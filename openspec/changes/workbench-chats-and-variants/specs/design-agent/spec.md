## ADDED Requirements

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

## MODIFIED Requirements

### Requirement: App access only through tools
The agent SHALL read and change app state only through the app's tool surface. At minimum the tools SHALL cover:
- reading and updating packs and style guides;
- creating assets, and listing, creating and renaming their variants;
- starting, reading, cancelling and retrying jobs;
- reading concept image selections, each hero's variant, and segmentation results;
- storing manifests;
- reading measured part colours and reading and editing the main palette and its variants;
- submitting part programs;
- reading build reports and scores.

Tools that act on a manifest, program, build or hero SHALL take an optional variant and use the asset's default
variant when it is omitted.

#### Scenario: Tool-made changes are visible
- **WHEN** the agent creates an asset through a tool
- **THEN** the asset appears in the UI without a page reload

#### Scenario: Program for a named variant
- **WHEN** the agent submits a program for the cart with variant "loaded"
- **THEN** it becomes the next version of the loaded variant and the default variant is unchanged

## REMOVED Requirements

### Requirement: Per-pack chat sessions
**Reason**: Replaced by "Multiple chats", which allows many chats per pack, and chats outside packs, each with a page
context.
**Migration**: Each pack's existing chat turns and Claude session become that pack's first chat, which is opened from
the chat list.
