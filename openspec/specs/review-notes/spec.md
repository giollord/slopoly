# review-notes Specification

## Purpose
Lets the user point at what is wrong with a build by painting on the reference and the model side by side and
commenting. The agent then gets structured, persistent notes that it works through.

## Requirements

### Requirement: Readable panes
The review window SHALL have a light and a dark theme that the user switches, kept for the next window. Strokes SHALL
be drawn see-through at one opacity, so overlapping strokes don't hide what is under them.

#### Scenario: Dark model
- **WHEN** the user reviews a dark model and switches to the light theme
- **THEN** both panes show the model on a light background, and the choice holds in the next review

### Requirement: Highlighted note images
A note's pane image SHALL show the painted area as in the original, a semi-transparent border of contrasting colours
around it, and the rest of the pane dimmed, with nothing blurred and no paint colour over the object. A pane without
strokes SHALL be stored as it was shown.

#### Scenario: Painted cowcatcher
- **WHEN** a note has strokes over the cowcatcher on the build pane and none on the reference pane
- **THEN** the build image shows the cowcatcher unchanged inside a border with the rest dimmed, and the reference
  image is the plain pane

### Requirement: Closing with unsent work
When the user closes the review window with notes not sent, a comment or strokes in progress, or verdicts on earlier
notes, the window SHALL ask whether to send them to the agent, close without sending, or keep the window open.
Sending from that question SHALL include the note in progress.

#### Scenario: Close with two notes
- **WHEN** the user has added two notes and closes the window
- **THEN** the window asks; choosing send stores both notes and finishes the job, choosing close finishes it as
  cancelled, and choosing cancel keeps the window open with the notes

#### Scenario: Close with nothing
- **WHEN** the user closes the window without notes, comment, strokes or verdicts
- **THEN** it closes without asking, and the job finishes as cancelled

### Requirement: Review window as a detached job
`slopoly review <target>` SHALL open a window for a variant's current build (or a given build), start a job and return
its id and the window's address at once. It SHALL show two panes side by side: on the left the reference, either the
hero image or the reference mesh (the user switches), and on the right the build.

#### Scenario: Open a review
- **WHEN** the agent runs `slopoly review orcish/locomotive`
- **THEN** a window shows the locomotive's reference beside its current build, and the command prints a job id and
  the window's address immediately

#### Scenario: Reference without a mesh
- **WHEN** the variant's reference hero has no reference mesh
- **THEN** the left pane shows the hero image, and the mesh choice is disabled with a reason

### Requirement: Locked cameras
Each 3D pane SHALL orbit, pan and zoom on its own. With lock on, the reference mesh pane SHALL follow the build
pane's camera exactly. With the hero image on the left, lock SHALL turn the build to the hero's camera direction,
which is the three-quarter front-left view.

#### Scenario: Lock on the mesh
- **WHEN** the user turns lock on and orbits the build pane
- **THEN** the reference mesh pane shows the same view direction and zoom

#### Scenario: Lock on the hero
- **WHEN** the left pane shows the hero image and the user turns lock on
- **THEN** the build pane snaps to the hero's camera direction and stays there until lock is turned off

### Requirement: Painting notes
The user SHALL be able to paint strokes on either pane or both, erase and clear them, and write a comment. While
strokes exist, both cameras SHALL stay still. Adding the note SHALL save it and clear the strokes and comment, so the
user can turn the model and add more notes. Notes SHALL be listed in the window, where the user can open, edit or
delete them before sending.

#### Scenario: Two notes
- **WHEN** the user paints the cowcatcher on both panes, comments "V in plan, wide at the bottom", adds the note,
  then turns to the stack, paints it, comments "more complex profile" and adds it
- **THEN** the window lists two notes, and each keeps its own strokes, camera and comment

#### Scenario: Comment without paint
- **WHEN** the user adds a note with a comment and no strokes
- **THEN** the note is saved with its camera and no hits

### Requirement: Note content for the agent
Sending SHALL finish the job with the notes. Each note SHALL give the comment, the camera, and an image per pane with
the strokes drawn in. It SHALL also give the build parts the strokes cover, each with its share. With a mesh on the
left, it SHALL give the painted region's bounds in metres. Results SHALL hold paths and numbers, never image data.

#### Scenario: Cowcatcher note
- **WHEN** the user's strokes on the build fall mostly on the cowcatcher and partly on the deck
- **THEN** the note lists `cowcatcher` with the larger share and `deck` with the smaller, with both pane images and
  the camera

#### Scenario: Window closed without sending
- **WHEN** the user closes the review window without sending
- **THEN** no notes are stored and the job finishes as cancelled

### Requirement: Part hits from the nearest surface
A painted pixel SHALL count only for the first build surface its camera ray meets, so hidden parts are never hit.
Pixels SHALL be weighted towards each stroke's centre line. Parts with less than 10 % of a note's weight SHALL be left
out. Strokes over empty space SHALL be reported as an `empty` share, with their region in metres where a reference mesh
is shown.

#### Scenario: Part behind a gap
- **WHEN** the user paints over a gap between the spokes, through which the frame behind is visible
- **THEN** the frame is hit only where the ray meets it first, and parts hidden behind the frame are not hit

#### Scenario: Missing part
- **WHEN** the user paints on empty space above the cab where the reference shows roof spikes
- **THEN** the note reports an `empty` share and that region's bounds on the reference mesh

### Requirement: Notes kept per variant
Sent notes SHALL be stored in the variant's folder, each with a number, the build it was made on and a status of
`open`, `addressed` or `wontfix`. The agent SHALL set the status with a command that records a short reason and the
build that addressed it. `slopoly status <target>` SHALL count open notes.

#### Scenario: Address a note
- **WHEN** the agent runs `slopoly note orcish/locomotive 3 addressed --by 15 --reason "slats fan out downwards"`
- **THEN** note 3 is `addressed` by build 15 with that reason, and `slopoly status` counts one fewer open note

### Requirement: Earlier notes in the next review
A review SHALL show the variant's earlier `addressed` notes as pins at their cameras. The user SHALL be able to
confirm each one as fixed or reopen it, or confirm all of them at once. Reopening SHALL set it back to `open` with the
user's comment. `slopoly status` SHALL count `addressed` notes the user hasn't confirmed as `unconfirmed`.

#### Scenario: Not fixed yet
- **WHEN** the user opens addressed note 3 in the next review, sees the slats still fan the wrong way and reopens it
  with "still wider at the top"
- **THEN** note 3 is `open` again with that comment in its history, and the job result lists it as reopened

#### Scenario: All fixed
- **WHEN** the next review shows 15 addressed notes and the user presses "All fixed" and sends
- **THEN** all 15 notes are closed, and `slopoly status` shows no unconfirmed notes
