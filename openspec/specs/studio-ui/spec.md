# studio-ui Specification

## Purpose
Management controls and navigation of the studio UI: concept page, concept and asset lists, asset editing.

## Requirements

### Requirement: Concept page
Each concept image SHALL have its own page with the full-size image, its prompt, seed, reference images, job and asset, selection and delete controls, and a box to ask the agent for changed variants with a chosen image count. A hero's page SHALL show its view images and a front-direction control, and a view's page SHALL link to its hero.

#### Scenario: Open a concept
- **WHEN** the user clicks a concept image in the gallery
- **THEN** its page opens showing the image at full size with prompt and seed

#### Scenario: Ask for changes
- **WHEN** the user writes "make the roof red" with count 3 and sends it
- **THEN** the pack's agent receives the request and starts a revision job for 3 images of that concept

#### Scenario: Hero with views
- **WHEN** the user opens a hero that has views
- **THEN** the page shows its front, side, top and back views and lets the user turn the front direction and remake them

### Requirement: Asset management
The Assets tab SHALL let the user create, edit, delete, search, filter by status and sort assets, and show each asset's triangle budget.

#### Scenario: Delete an asset
- **WHEN** the user deletes an asset and confirms
- **THEN** it and its concepts, manifest, programs and builds are removed from the pack

### Requirement: Manual asset editing and navigation
The asset page SHALL let the user edit the asset's name, description and triangle budget, edit its manifest, and submit a hand-edited part program as a new version. Asset, concept and scene pages SHALL show breadcrumbs back to the pack tab they belong to, and pack tabs SHALL be addressable by URL.

#### Scenario: Back to the assets list
- **WHEN** the user opens an asset from the Assets tab and clicks the "Assets" breadcrumb
- **THEN** the pack page opens on the Assets tab

### Requirement: Concept management by kind
The Concepts tab SHALL let the user generate new style anchors and heroes with a description and count, delete concepts, filter by kind, asset and selection, and show style anchors, heroes and views in separate groups. A picked hero SHALL offer an action that makes its views.

#### Scenario: Filter heroes of one asset
- **WHEN** the user chooses kind "Heroes" and asset "cart"
- **THEN** only the cart's hero images are shown

#### Scenario: Make views
- **WHEN** the user picks a cart hero and chooses "Make views"
- **THEN** a views job starts, and the view images appear under the hero when it finishes
