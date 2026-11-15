# asset-packs Specification

## Purpose
Organizes generated content into packs. Each pack carries the shared instructions and style guide, and owns assets with their concept images, manifests, part-program versions and builds.

## Requirements

### Requirement: Packs with instructions and style guide
A pack SHALL have a name, general instructions and a style guide. The style guide consists of style text and zero or more reference images. All of these SHALL be editable.

#### Scenario: Create a pack
- **WHEN** the user creates a pack with name "Gnome village", instructions and style text, and uploads two reference images
- **THEN** the pack is listed with its instructions, style text and both images

#### Scenario: Edit a style guide
- **WHEN** the user changes the style text or removes a reference image
- **THEN** later generation jobs for that pack use the updated style guide

### Requirement: Assets within a pack
A pack SHALL own assets. Each asset has a name, a short description and a status reflecting its furthest completed stage: concept, manifest, built or validated.

#### Scenario: Asset added by the agent
- **WHEN** the agent proposes a "wooden cart" asset for the pack
- **THEN** the asset appears in the pack with status concept and its description

### Requirement: Concept images with selection
Generated images SHALL be stored as concept images linked to their pack or asset and their originating job. Their kind is style anchor, hero or view, and a view SHALL be linked to the hero it was rendered from. The user SHALL be able to mark anchors and heroes picked or rejected. Only picked images SHALL be used as references for later steps, and the views of a hero are usable while the hero is picked.

#### Scenario: Reject an image
- **WHEN** the user rejects a hero image of the cart
- **THEN** it is hidden from the default gallery view and no longer offered to the agent as a reference

#### Scenario: Regenerate on request
- **WHEN** the user asks for more variants of a concept
- **THEN** new images are added alongside the existing ones and are neither picked nor rejected

#### Scenario: Deleting a hero removes its views
- **WHEN** the user deletes a hero that has views
- **THEN** its views and their masks are deleted with it

#### Scenario: A hero and its views share a variant
- **WHEN** views are rendered from the cart's picked hero
- **THEN** they belong to the hero's variant, and that variant has no other picked hero (see asset-variants)

#### Scenario: New heroes go to the requested variant
- **WHEN** hero images are generated for the cart's "loaded" variant
- **THEN** they belong to the loaded variant, and hero jobs that name no variant add their images to the default
  variant

### Requirement: Versioned part programs and builds
Each submitted part program SHALL be stored as a new immutable version of one variant of its asset. Each build of a version SHALL keep its exported model, validator report and silhouette scores.

#### Scenario: Roll back
- **WHEN** a new program version fails validation
- **THEN** earlier versions of that variant and their builds remain available, and any earlier version can be marked
  as the variant's current version

### Requirement: File access over the API
Images, masks, programs and exported models SHALL be stored as files. The API SHALL let the UI, the workers and the agent download them and let workers upload them.

#### Scenario: Worker uploads output
- **WHEN** a worker finishes a job and uploads its output files
- **THEN** the files are downloadable through the API and linked to the job's pack or asset

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
The user SHALL be able to delete a concept image; its part masks are removed with it.

#### Scenario: Delete a turnaround
- **WHEN** the user deletes a segmented turnaround
- **THEN** the image and its masks no longer appear for the user or the agent

### Requirement: Pack deletion
The user SHALL be able to delete a pack from the pack list or the pack page, confirming by typing the pack's name. Deleting SHALL first cancel the pack's queued and running jobs. It SHALL then remove the pack with its style references, assets, variants, concepts, masks, manifests, programs, builds, scenes, palette, palette variants, jobs and chats. Knowledge notes SHALL stay.

#### Scenario: Delete a pack
- **WHEN** the user deletes "Gnome village" and types its name to confirm
- **THEN** the pack disappears from the pack list, its pages and chats are no longer reachable, and the knowledge notes
  are unchanged

#### Scenario: Running jobs are cancelled
- **WHEN** the user deletes a pack while one of its image jobs is running
- **THEN** the job is cancelled, its worker discards the result, and nothing is attached to the deleted pack

#### Scenario: Wrong name
- **WHEN** the typed name does not match the pack's name
- **THEN** the delete button stays disabled
