# Design

## 1. Concept revisions

`revise_concept(conceptImageId, change?, count)` copies the source job's inputs, sets `seed = null` and the count,
and resubmits the job with the same operation.

**With a change.** The tool also does two things:

- It appends the change to the prompt: `"Change from image 1: <change>"`.
- It puts the concept's own file first in `references`, trimmed to the three-reference limit. FLUX.2 klein is an
  edit model, so this keeps the image recognisable while it applies the change.

**Where requests come from.**

- On the concept page, the UI doesn't call the tool directly. It sends a chat turn to the pack's agent:
  `Revise concept <id>: <text>. Make <n> images.` The agent decides how to phrase the change and calls
  `revise_concept`.
- The REST endpoint `POST /api/concepts/{id}/revise` exists for tests and scripts.

**Seeds.** The comfy worker already reports the seed of each image. `ConceptImage.Seed` stores it, so the concept
page can show it.

## 2. Deleting concepts

`DELETE /api/concepts/{id}` removes the concept image and its part masks. Files are kept; they are content-addressed
and may be shared. Builds keep their copies of their inputs, so old builds still make sense after a deletion.

## 3. UI structure

**Pack page tabs** come from `?tab=style|concepts|assets|scenes|palette|jobs`. Changing tab updates the URL with
`NavigationManager.NavigateTo(replace: true)`.

**Breadcrumbs.** The asset, concept and scene pages use `MudBreadcrumbs` to link back to the right tab.

**Concepts tab.**

- A filter row holds a kind toggle (All / Style anchors / Turnarounds), an asset select and a selection select
  (Not rejected / Picked / Undecided / Rejected / All).
- A "New" button opens a `MudDialog` with:
  - the operation;
  - the asset, for turnarounds;
  - the description;
  - the count.
- With "All", the images are grouped under headers.
- Clicking an image opens its concept page. The cards keep the pick, reject and delete buttons; delete asks for
  confirmation with `DialogService.ShowMessageBoxAsync`.

**Assets tab.** The table is a `MudDataGrid` with:

- a quick filter;
- a status filter;
- sortable columns;
- a budget column;
- an actions column (open, edit, delete).

Create and edit share one dialog component.

**Asset page.**

- An "Edit" dialog changes the name, description and budget.
- The Manifest section has an editable JSON field with a Save button.
- The Programs section has a "New version" editor, prefilled with the current source, with a note field and a
  Submit button.

## 4. Per-asset budget

`Asset.PolyBudget` is an `int?`. The budget a build uses is `asset.PolyBudget ?? pack.PolyBudget`, and it goes into
the build inputs. The agent's tools are:

- `create_asset(..., polyBudget?)`;
- `update_asset(assetId, name?, description?, polyBudget?)`.

`agent/CLAUDE.md` gives rough sizes: props 300–800, buildings 800–2000, characters 1500–4000.

## 5. Scenes

### Records

| Record | Fields |
|---|---|
| `Scene` | Id, PackId, Name, Description, Placements, GlbFileId?, Report?, UpdatedAt |
| `ScenePlacement` (record) | Name, AssetId, At (x, y, z), Rot (Euler degrees, optional), Scale |

Placements are stored as one JSON column of the scene; they are always saved together. Units are metres with Y up,
matching `slopoly_model`.

### Saving and building

`save_scene(packId, name, description, placements[])` creates the scene, or replaces its placements, matched by
name within the pack. It then queues a geometry job of kind `scene` (a scene without placements is saved unbuilt).

The job inputs are `{sceneId, placements: [{name, glbFileId, at, rot, scale}]}`. Each placement uses its asset's
latest build of the current program version. An asset without a build is refused, with its name in the error.

### The scene job

The worker runs `slopoly_model.scene` in a subprocess. It imports each GLB with Blender's glTF importer (already in
the image, so no new dependency) under an empty named after the placement, shares one palette material, and exports
a GLB. The report contains:

- `placements`: name, world bounds, and whether the placement is `grounded` (its lowest point is within 2 cm of
  y = 0, or of the top of another placement under it);
- `overlaps`: pairs whose world bounding boxes intersect by more than 10 % of the smaller box's volume.

Bounding boxes are enough for placing assets. The agent fixes overlaps and floating placements, and the user
judges the rest by looking.

### Result handling

`SceneResults` stores the GLB and the report on the scene. The `Scenes` tab:

- lists the scenes;
- opens `/scenes/{id}`, which shows a `<model-viewer>`, a placement table with editable numbers, add and remove
  rows, Save (rebuild), and the report.

### Agent help

`get_scene(sceneId)` returns the placements and the report. `get_pack` gains each asset's bounds from its latest
build, so the agent can place assets without reading build reports.

## 6. Knowledge base

### Notes

The notes live in `knowledge/<slug>.md` at the repo root. Each note has front matter:

```markdown
---
title: Hollow containers
tags: [container, cart, crate, inset, extrude]
summary: Open-topped boxes (cart beds, crates, troughs) with inset + negative extrude.
---
```

### Location

The AppHost sets `Slopoly__KnowledgeDir` to `<repo>/knowledge`. The API is a host process, so it reads and writes
the folder directly. No container mount is needed, and new notes appear in `git status` for the developer to
commit. If the setting is missing, the API falls back to `<data-dir>/knowledge`, for a deployment without the repo.

### KnowledgeService

`KnowledgeService` parses front matter with YamlDotNet, a popular and maintained library. It does a simple
search: it scores query terms against the title, tags, summary and body, then returns the top matches with their
summaries. Notes are few and small, so it doesn't need an index.

Writes do three things:

- validate the slug;
- keep the front matter;
- refuse paths outside the folder.

### Tools and UI

**MCP tools:**

- `search_knowledge(query)`, which returns slug, title, summary and score;
- `read_knowledge(slug)`;
- `write_knowledge(slug, title, tags, summary, body)`.

**REST endpoints:** the same operations, plus delete, for the Knowledge page. The page lists notes and has a search
box, an editor for the front matter and the Markdown body (monospace; no rendered preview, which would need a
non-core package), and save and delete buttons.

### Agent rules

- Before writing a manifest or program, `search_knowledge` for the asset's kind and its notable features. Apply the
  notes that match.
- When the user asks for a technique, or a fix works after several attempts, write or update a note in general
  terms rather than in terms of this pack.

## 7. `jitter`

`jitter(shape, amount, seed=0, faces=None)` moves each vertex of the selected faces by a seeded random offset of up
to `amount` metres.

- Shared vertices move once, so the mesh stays closed.
- Faces stay planar only approximately, which is acceptable for low poly; the GLB export triangulates them anyway.
- The silhouette and validation code needs no changes.

**Chips** are a `bevel` followed by a small `jitter`.

**Cracks** are a thin `box` subtracted with `boolean`, with its faces tagged with a darker role ("wood crack"). The
notes document both.

## Non-goals

- No physics-based scene placement and no automatic layout solver.
- No knowledge-base embeddings.
- No hosted multi-user access to the knowledge folder.
