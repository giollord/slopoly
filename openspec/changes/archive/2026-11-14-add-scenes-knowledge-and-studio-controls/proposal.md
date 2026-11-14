# Proposal

## Why

The first hands-on check of the foundation found gaps in the studio. Concepts and assets can't be managed: you can't
create, delete, filter or edit them, open a large view, or navigate back. The only way to vary an image is a fixed
"two more" button. Assets share one pack-wide triangle budget. The agent can't put assets together into a scene.
The agent also forgets modelling techniques between packs, which is why the generated cart had no hollow bed and no
wear.

## What Changes

- **Concept page.** Clicking a concept opens `/concepts/{id}`. It shows:
  - the full-size image;
  - the prompt, seed, references, count, job and asset;
  - selection and delete controls;
  - a "change with the agent" box: the user describes the change, picks how many images, and the agent runs ComfyUI.
- **Concept revisions.** `more_variants` becomes `revise_concept(conceptImageId, change?, count)`. It reruns the
  concept's generation with a fresh seed. With a change, it also adds the change to the prompt and uses the concept
  itself as the first reference image. The fixed "more variants" button goes away.
- **Concepts tab controls:**
  - new style anchors and new turnarounds, with a description and a count;
  - delete;
  - filters by kind, asset and selection;
  - style anchors (scenes) and turnarounds (single objects) in separate sections.
- **Assets tab controls:** create, edit and delete in dialogs, a search box, a status filter, sorting, and a
  triangle-budget column.
- **Asset editing and navigation.**
  - The asset page has breadcrumbs (Packs › pack › Assets › asset). Each pack tab has its own URL (`?tab=assets`).
  - On the asset page you can edit the name, description and triangle budget, edit the manifest JSON, and edit and
    submit the part program by hand.
- **Per-asset triangle budget.** `Asset.PolyBudget`, when set, overrides the pack default for that asset's builds.
  The agent sets it when it creates an asset (characters need more triangles than a brick).
- **Scenes.** A pack can hold scenes that place built assets with a position, rotation and scale.
  - A geometry `scene` job combines the assets' current GLBs into one GLB.
  - It reports each placement's bounds, overlaps between placements and placements that float.
  - The agent assembles scenes through tools, and the user can view and adjust them on a new Scenes tab.
- **Global knowledge base.** Technique notes are Markdown files in the repo's `knowledge/` folder, for example
  "hollow containers" or "wear, chips and cracks".
  - The API reads and writes the folder directly; it runs on the host next to the repo.
  - The agent searches and reads notes before modelling. It writes or updates a note when the user asks for a
    technique, or when it finds one worth reusing.
  - A Knowledge page lists, searches and edits the notes.
  - Notes are global, not per pack, and new notes show up in git like any other repo file.
- **Imperfections in the part library.** A new `jitter(shape, amount, seed, faces)` operation adds small irregular
  deformations. It moves shared vertices together, so the mesh stays closed. The first notes show how to make
  chips, cracks (shallow darker grooves) and hollow beds with the existing operations.

## Capabilities

### New Capabilities

- `scenes`: scene records, the scene build job and its report, and agent assembly.
- `knowledge-base`: repo-backed global technique notes, the agent's search, read and write tools, and the UI page.
- `studio-ui`: concept page, concept and asset controls, asset editing and navigation.

### Modified Capabilities

- `asset-packs` (from the unarchived foundation change): per-asset triangle budget, concept deletion, and concept
  revision on request.

## Impact

- **Contracts and storage.**
  - New fields: `Asset.PolyBudget`, `ConceptImage.Seed`.
  - New entity `Scene` with its placements as a JSON column, with an EF migration.
- **API.**
  - New REST endpoints for deleting concepts, editing and deleting assets, scenes and knowledge notes.
  - MCP tools: `revise_concept` (replaces `more_variants`), `update_asset`, `get_scene`, `save_scene`,
    `search_knowledge`, `read_knowledge` and `write_knowledge`.
- **Geometry worker.** A new `scene` job kind (Blender glTF import/export) and `jitter` in `slopoly_model`.
- **AppHost.** Passes the knowledge folder path to the API.
- **Agent.** `agent/CLAUDE.md` gains rules for the knowledge base and for scenes.
