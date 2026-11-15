# Spec Delta

## Purpose

Gives the user small desktop windows for what a terminal and an agent chat do badly: choosing among images and
looking at 3D builds. The agent opens them through the CLI and receives the user's choices as job results.

## ADDED Requirements

### Requirement: Pick window as a detached job
`slopoly pick <image set>` SHALL open a window that shows the set's images, start a job and return its id at once,
without waiting for the user. The image sets SHALL include a pack's style anchors, an asset's heroes and any list of
image paths. A free-text question with options SHALL also be supported.

#### Scenario: Agent asks for a hero
- **WHEN** the agent runs `slopoly pick gnome-village/cart --heroes`
- **THEN** a window shows the cart's undecided heroes, with its variants' current references shown apart, and the
  command prints a job id immediately

### Requirement: User choices recorded in files
In the pick window the user SHALL be able to pick images and write an optional note, then confirm. There SHALL be no
separate reject action: confirming SHALL reject every shown image the user did not pick. Confirming SHALL write the
selection states to the images' metadata files, close the window and finish the job with the picked and rejected paths
and the note as its result. Rejected images SHALL move to a `rejected/` folder beside them (see pack-workspace).

#### Scenario: Pick with a note
- **WHEN** the user picks hero 3 out of heroes 1 to 3, writes "make the wheels bigger" and confirms
- **THEN** hero 3 is picked, heroes 1 and 2 are moved to `heroes/rejected/`, the window closes, and `slopoly wait` on
  the job returns the picked and rejected paths and the note

#### Scenario: Window closed without confirming
- **WHEN** the user closes the pick window without confirming
- **THEN** no selection state changes and the job finishes as cancelled

### Requirement: Readable pick cards
Text under the images in the pick window (name, seed, prompt) SHALL be shown whole or clamped to whole lines, never cut
through a line, and a clamped prompt SHALL open in full on click.

#### Scenario: Long prompt
- **WHEN** a hero's prompt is longer than three lines
- **THEN** its card shows three whole lines, and clicking the text shows all of it

### Requirement: Pick limits and a variant per hero
A pick SHALL be limitable to a number of images. Several heroes MAY be picked at once. Each picked hero SHALL have a
variant name field, suggested as the default variant while it has no reference and as new names after that. When two
or more heroes are picked, the window SHALL warn that each pick creates (or replaces the reference of) its own variant.
A name of an existing variant SHALL be marked as replacing that variant's reference (see asset-variants).

#### Scenario: Second hero
- **WHEN** the user picks heroes C and D of a cart whose default variant has no reference
- **THEN** the window suggests "default" for C and a new variant name for D, warns that each pick makes its own
  variant, and the job result lists both variants with their references

### Requirement: View window
`slopoly view <target>` SHALL open a window with the 3D viewer (see asset-viewer) for a variant's current build, a
given build or a scene, and return at once. For a build it SHALL also show each view's comparison image with its
object score, the validation summary and the shading defect counts.

#### Scenario: Look at the cart
- **WHEN** the agent or user runs `slopoly view gnome-village/cart`
- **THEN** a window shows the cart's current build in the 3D viewer, with its comparison images and scores beside it

#### Scenario: Live refresh
- **WHEN** a view window shows a variant's current build and a new build becomes current
- **THEN** the window loads the new build without being reopened

### Requirement: Browser fallback
When no native window can be opened, the pick and view commands SHALL serve the same page on a local address bound to
the loopback interface, open it in the default browser, and include the address in their result. After a pick is
confirmed, the page SHALL tell the user they can close the tab.

#### Scenario: No GUI backend
- **WHEN** `slopoly pick` runs on a machine where the native window library has no backend
- **THEN** the page opens in the browser, the result includes its local address, and confirming records the choice as
  in the window
