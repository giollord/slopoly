## MODIFIED Requirements

### Requirement: Concept images with selection
Generated images SHALL be stored as concept images linked to their pack or asset and their originating job. Their kind is style anchor, hero or view, and a view SHALL be linked to the hero it was rendered from. A hero and its views SHALL belong to one variant of their asset. The user SHALL be able to mark anchors and heroes picked or rejected; a variant has at most one picked hero (see asset-variants). Only picked images SHALL be used as references for later steps, and the views of a hero are usable while the hero is picked.

#### Scenario: Reject an image
- **WHEN** the user rejects a hero image of the cart
- **THEN** it is hidden from the default gallery view and no longer offered to the agent as a reference

#### Scenario: Regenerate on request
- **WHEN** the user asks for more variants of a concept
- **THEN** new images are added alongside the existing ones and are neither picked nor rejected

#### Scenario: Deleting a hero removes its views
- **WHEN** the user deletes a hero that has views
- **THEN** its views and their masks are deleted with it

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

## ADDED Requirements

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
