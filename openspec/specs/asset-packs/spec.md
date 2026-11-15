# asset-packs Specification

## Purpose
Organizes generated content into packs. Each pack carries the shared instructions and style guide, and owns assets with their concept images, manifests, part-program versions and builds.

## Requirements

### Requirement: Packs with instructions and style guide
A pack SHALL have a name, general instructions and a style guide. The style guide consists of style text and zero or
more reference images. The instructions and style text SHALL be stored in the pack's `style.md`, and the reference
images in its style folder. All of them SHALL be editable as files.

#### Scenario: Create a pack
- **WHEN** the agent runs `slopoly pack new gnome-village`, writes instructions and style text into `style.md` and
  copies two reference images into the style folder
- **THEN** `slopoly status gnome-village` shows the pack with its style text and both images

#### Scenario: Edit a style guide
- **WHEN** the user changes the style text or removes a reference image
- **THEN** later generation jobs for that pack use the updated style guide

### Requirement: Assets within a pack
A pack SHALL own assets. Each asset has a name, a short description and a status reflecting its furthest completed
stage: concept, manifest, built or validated. The status SHALL be derived from the asset's files.

#### Scenario: Asset added by the agent
- **WHEN** the agent runs `slopoly asset new gnome-village/cart --description "wooden hand cart"`
- **THEN** the asset appears in `slopoly status` with status concept and its description

### Requirement: Concept images with selection
Generated images SHALL be stored as concept images in their pack's or variant's folder, with metadata naming their
originating job. Their kind is style anchor, hero or view, and a view SHALL be linked to the hero it was rendered from.
The user SHALL be able to mark anchors and heroes picked or rejected in the pick window, and the agent with a CLI
command. Only picked images SHALL be used as references for later steps, and the views of a hero are usable while the
hero is picked.

#### Scenario: Reject an image
- **WHEN** the user rejects a hero image of the cart
- **THEN** it is no longer offered in pick windows by default or used by the CLI as a reference

#### Scenario: Regenerate on request
- **WHEN** the user asks for more variants of a concept
- **THEN** new images are added alongside the existing ones and are neither picked nor rejected

#### Scenario: Deleting a hero removes its views
- **WHEN** the agent deletes a hero that has views with `slopoly rm`
- **THEN** its views and their masks are deleted with it

#### Scenario: A hero and its views share a variant
- **WHEN** views are rendered from the cart's picked hero
- **THEN** they belong to the hero's variant, and that variant has no other picked hero (see asset-variants)

#### Scenario: New heroes go to the requested variant
- **WHEN** hero images are generated for the cart's "loaded" variant
- **THEN** they belong to the loaded variant, and hero jobs that name no variant add their images to the default
  variant

### Requirement: Versioned part programs and builds
Each build of a variant SHALL get the next build number of that variant and keep a copy of the program it was built
from, with its exported model, validator report and silhouette scores. Build folders SHALL NOT be changed after the
build, except when a palette refresh replaces the palette texture in their models.

#### Scenario: Roll back
- **WHEN** a new build fails validation
- **THEN** earlier builds of that variant remain available, and `slopoly build use` makes an earlier build the
  variant's current build and restores its program as the variant's `program.py`

### Requirement: Per-asset triangle budget
An asset MAY have its own triangle budget. Builds SHALL use the asset's budget when it is set and the pack's budget otherwise.

#### Scenario: Character with a larger budget
- **WHEN** the pack budget is 2000 and the "gnome" asset has budget 3500
- **THEN** a 3000-triangle gnome build passes the budget check and a 3000-triangle cart build does not

### Requirement: Concept revision on request
On request the agent SHALL generate new images from a concept's generation with a fresh seed and a user-chosen count, optionally applying a described change with the concept itself as the first reference. New images SHALL start neither picked nor rejected. Each concept SHALL record the seed it was generated with.

#### Scenario: Changed variants
- **WHEN** the agent revises a concept with change "add a red roof" and count 2
- **THEN** two new undecided images appear, generated with the concept as first reference and the change in the prompt

### Requirement: Concept deletion
The user and the agent SHALL be able to delete a concept image with `slopoly rm`. Its metadata and part masks are
removed with it.

#### Scenario: Delete a turnaround
- **WHEN** the agent deletes a segmented hero's views
- **THEN** the view images, their metadata and their masks no longer exist in the workspace

### Requirement: Pack deletion
Deleting a pack SHALL be deleting its folder. `slopoly pack rm <pack> --yes` SHALL first cancel the pack's queued and
running jobs and then delete the folder. A job whose pack folder is gone when it finishes SHALL fail without writing
any file. Knowledge notes SHALL stay.

#### Scenario: Delete a pack
- **WHEN** the user runs `slopoly pack rm gnome-village --yes`
- **THEN** the pack's folder is gone, it no longer appears in `slopoly status`, and the knowledge notes are unchanged

#### Scenario: Running jobs are cancelled
- **WHEN** the user deletes a pack while one of its image jobs is running
- **THEN** the job is cancelled, nothing is written, and the pack folder is not recreated

#### Scenario: Confirmation required
- **WHEN** `slopoly pack rm gnome-village` runs without `--yes`
- **THEN** it fails with code `confirm_required` and deletes nothing

#### Scenario: Wrong name
- **WHEN** `slopoly pack rm gnome-vilage --yes` names no existing pack
- **THEN** it fails with code `not_found`, lists the existing packs and deletes nothing
