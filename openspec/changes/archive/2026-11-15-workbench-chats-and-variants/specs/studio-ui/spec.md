## ADDED Requirements

### Requirement: Asset page layout
The top of the asset page SHALL show the variant picker, the 3D viewer, the embedded chat, the palette choice and the
Export button. The other asset information SHALL be in collapsible sections below them: reference, build comparison,
builds, build report, manifest, program versions and new program version. Only the reference section SHALL start open.

#### Scenario: Open an asset
- **WHEN** the user opens the cart's asset page
- **THEN** the viewer, the chat, the palette choice and Export are visible without scrolling on a desktop screen, the
  reference section is open and the other sections are collapsed

#### Scenario: Switch variant
- **WHEN** the user picks the "loaded" variant
- **THEN** the viewer, the sections and the chat's context switch to the loaded variant's builds, versions and
  reference

### Requirement: Reference hero on the asset page
The asset page's reference section SHALL show the selected variant's reference hero with its views, each linking to
its concept page. It SHALL also show the variant's other heroes that are not rejected, with actions to pick one as the
reference or start a new variant from it.

#### Scenario: Look at the hero while modelling
- **WHEN** the user opens the cart's asset page
- **THEN** the reference section shows the picked hero and its front, side, top and back views next to each other

#### Scenario: No reference yet
- **WHEN** the selected variant has no picked hero
- **THEN** the reference section says so and lists the asset's undecided heroes with a pick action

### Requirement: Paged history lists
The lists of jobs, builds, program versions and chats SHALL be paged, with a page size the user can change. Page
contents SHALL be loaded from the server one page at a time, newest first, with the total count shown. Live updates
SHALL refresh the current page. Asset parts and build report tables SHALL stay unpaged.

#### Scenario: Many jobs
- **WHEN** a pack has 600 jobs and the user opens the Jobs tab
- **THEN** the newest 25 jobs are shown with the total of 600 and page controls, and moving to page 2 loads jobs 26 to 50

#### Scenario: New build while on page 1
- **WHEN** a build finishes while the user views the first page of builds
- **THEN** the new build appears at the top of the page without a reload

### Requirement: Long chats load in steps
A chat SHALL first load its newest turns and SHALL offer a control to load earlier turns.

#### Scenario: Old chat
- **WHEN** the user opens a chat with 80 turns
- **THEN** the newest 20 turns are shown, and "Load earlier" adds the 20 before them

### Requirement: Chat drawer on every page
Every page SHALL offer an agent button that opens a chat drawer with the current chat, the chat list and "New chat".
A chat started from the drawer SHALL take the page's context.

#### Scenario: Chat from a concept page
- **WHEN** the user opens the drawer on a hero's concept page and starts a new chat
- **THEN** the chat records that hero as its context

## MODIFIED Requirements

### Requirement: Manual asset editing and navigation
The asset page SHALL let the user edit the asset's name, description and triangle budget, add, rename and delete
variants, edit the selected variant's manifest, and submit a hand-edited part program as a new version of the selected
variant. Asset, concept and scene pages SHALL show breadcrumbs back to the pack tab they belong to, and pack tabs and
the selected variant SHALL be addressable by URL.

#### Scenario: Back to the assets list
- **WHEN** the user opens an asset from the Assets tab and clicks the "Assets" breadcrumb
- **THEN** the pack page opens on the Assets tab

#### Scenario: Link to a variant
- **WHEN** the user opens a link to the cart's asset page with the "loaded" variant
- **THEN** the page opens with the loaded variant selected

### Requirement: Build comparison on the asset page
The asset page SHALL show, in its build comparison section, each view's comparison image and object score for the
selected build, so the user can see where the model differs from the variant's reference views.

#### Scenario: Compare the cart
- **WHEN** the user opens the cart's asset page after a build against its views and expands the build comparison
  section
- **THEN** the section shows the front, side, top and back comparisons with their object scores, and selecting an
  older build shows that build's comparisons
