# Tasks

## 1. Data and API

- [x] 1.1 Add `Asset.PolyBudget`, `ConceptImage.Seed`, `Scene` and `ScenePlacement` with an EF migration. Store the
      seed in `ConceptImageResults`, and use `asset.PolyBudget ?? pack.PolyBudget` in the build inputs.
- [x] 1.2 Asset edit and delete. Deleting cascades to concepts, masks, the manifest, programs and builds. Add
      `PATCH`/`DELETE /api/assets/{id}`.
- [x] 1.3 Concept deletion with its masks (`DELETE /api/concepts/{id}`). Replace "more variants" with
      `revise_concept` (change and count) in the service, REST and MCP.
- [x] 1.4 MCP: `update_asset`, `create_asset` with a budget, and asset bounds in `get_pack`.
- [x] 1.5 .NET tests: the budget override, concept deletion, revision inputs, and asset deletion.

## 2. Knowledge base

- [x] 2.1 `KnowledgeService` (YamlDotNet front matter, search, read, write, delete, slug checks).
      `Slopoly__KnowledgeDir` comes from the AppHost.
- [x] 2.2 REST endpoints and the MCP tools `search_knowledge`, `read_knowledge` and `write_knowledge`.
- [x] 2.3 Initial notes in `knowledge/`: hollow containers, wear (chips, cracks and dents), and triangle budgets by
      asset kind.
- [x] 2.4 Tests: round trip, search ranking, and a refused traversal slug.

## 3. Geometry

- [x] 3.1 `jitter` in `slopoly_model`, documented in `agent/docs/slopoly_model.md`, with a test that the mesh stays
      closed.
- [x] 3.2 The `scene` job in the geometry worker (Blender glTF import): a combined GLB and a report with bounds, grounded
      and overlaps. Test it in a container.
- [x] 3.3 Scenes in the API: `save_scene` and `get_scene` (service, REST, MCP), the `SceneResults` handler, and a
      test.

## 4. UI

- [x] 4.1 Pack tabs addressable by URL, plus breadcrumbs on the asset, concept and scene pages.
- [x] 4.2 Concepts tab: a filter row, kind groups, a New dialog, delete with confirmation, and click to open. Remove
      the more-variants button.
- [x] 4.3 Concept page: the full image, prompt, seed and references, selection and delete, and "change with the
      agent" (text and count, sent as a chat turn).
- [x] 4.4 Assets tab: a data grid with search, a status filter, sorting, a budget column, and create, edit and delete
      dialogs.
- [x] 4.5 Asset page: an edit dialog, a manifest editor, and a program editor that submits a new version.
- [x] 4.6 Scenes tab and scene page: a viewer, a placement editor, rebuild, and the report.
- [x] 4.7 Knowledge page: a list with search, an editor with a preview, and create, save and delete. Add it to the
      app bar.

## 5. Agent and verification

- [x] 5.1 `agent/CLAUDE.md`: knowledge rules, budgets by kind, revisions, and scenes.
- [x] 5.2 Run all tests (.NET and containers) and check the new pages in the browser with small screenshots.
