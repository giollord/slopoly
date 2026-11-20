# design-agent Specification

## Purpose
Provides the conversational AI that turns a user's brief into a pack's style guide, concept images and part programs. It runs Claude Code on the user's own subscription and acts on the app only through a defined tool surface.

## Requirements

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

### Requirement: Agent models by techniques
The agent's instructions SHALL tell it to build parts from primitives transformed by modifiers, vertex groups,
cloning, mirroring and booleans, starting from the matching technique note, and to place individual vertices only for
2D profiles and curve control points.

#### Scenario: Wheeled object
- **WHEN** the agent designs an asset with wheels
- **THEN** it searches the notes, and its program builds the wheels from the wheeled-object technique (a rim, a spoke
  cloned around the axle, and mirrored wheels) rather than listing vertex coordinates

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

### Requirement: Agent plans part shapes
The agent's instructions SHALL require a shape plan in the manifest for every part of an asset with more than about
eight parts, and for every distinctive part of smaller ones, before the first build. A plan describes the part's
shape character: plan shape, profile, bends, where its ends are, and what it touches. It also gives the construction
steps in modelling operations and the checks.

#### Scenario: Steam pipe
- **WHEN** the agent plans a steam pipe that narrows and flares
- **THEN** its manifest entry describes the pipe's profile and gives steps such as a cylinder, one end scaled down,
  extruded and flared out, before `program.py` is written

### Requirement: Agent checks plans against close-ups
Before the first build, the agent SHALL look at a `look` close-up of each distinctive part's reference region. It SHALL
correct a plan that disagrees with the close-up. After a build, it SHALL compare the part with the same close-up.
The user SHALL NOT be asked to approve plans; they correct them through review notes.

#### Scenario: Bone ends
- **WHEN** the close-up of the ribs shows the knobbed ends at the top beside the spine
- **THEN** the rib plan places the ends at the top, and the agent checks the built ribs from the same camera

### Requirement: Agent works through review notes
After a build worth showing, the agent SHALL open a review (see review-notes) and wait for the notes. It SHALL treat
each note's comment as authoritative and its part hits as hints. It SHALL address the notes in order, setting each
note's status with a reason. A note it cannot fix SHALL be set to `wontfix` and explained to the user.

#### Scenario: Hit on a neighbour
- **WHEN** a note says "cowcatcher should be a V" and its hits list the cowcatcher at 80 % and the deck at 20 %
- **THEN** the agent changes the cowcatcher and leaves the deck as it is

### Requirement: Stop criterion with user notes
Before any user review, the agent SHALL stop at the silhouette bar: the build is validated, the mean object IoU is at
least 0.8 and no view's IoU is below 0.7. After a review, it SHALL stop only when the build is validated, the variant
has no open notes, and every IoU drop since the review is explained in its report. A drop caused by a change the user
asked for SHALL count as explained.

#### Scenario: Longer cowcatcher lowers IoU
- **WHEN** the user's note makes the agent lengthen the cowcatcher and the side IoU drops from 0.77 to 0.71
- **THEN** the agent reports the drop as caused by note 1, and the drop does not keep it iterating
