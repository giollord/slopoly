## Why

The asset and scene pages have become hard to work on. Everything sits in one long column, the history tables (jobs,
builds, program versions) grow without limit, and the only way to talk to the agent is a single per-pack chat in a
drawer that knows nothing about what the user is looking at. The viewer cannot show wireframe, grid, axes or normals,
so shading problems (dark patches, faces that light up wrongly) are hard to diagnose, and the geometry worker has no
step that repairs normals. Finally, an asset can only have one look: when two heroes of the same asset are picked, the
build silently compares against the newest one, and there is no way to keep a second version of an asset (for example
an empty cart and a loaded cart) with its own concepts and history.

## What Changes

- **3D viewer with overlays.** One shared viewer component for asset and scene models, with toggles for wireframe, a
  ground grid, the origin axes and vertex normals, plus the existing palette switch. It replaces `<model-viewer>`,
  which cannot draw these overlays.
- **Chats with page context.**
  - The user can start a new chat with the agent at any time, from any page, and switch between earlier chats.
  - A new chat records the page it was started on. Its first message carries a context block that names that page and
    its objects (pack, asset, variant, build, scene or concept) with their ids, so the agent can act without asking.
    Later messages carry a one-line note of the page the user is on.
  - The asset page and the scene page embed the chat next to the model.
  - **BREAKING (data):** the single per-pack chat becomes the pack's first chat. Existing turns and the Claude session
    are kept.
- **Stop the agent.** A Stop button ends the running agent turn and drops queued ones. The conversation keeps what was
  said up to the stop, so the next message continues the same session.
- **Asset page layout.** The top of the page shows the variant picker, the 3D viewer with its overlays, the chat, the
  palette choice and Export. Everything else sits below in collapsible sections: reference (the picked hero and its
  views, open by default), build comparison, builds, build report, manifest, program versions and the program editor.
- **Asset variants.**
  - An asset has one or more variants. Each variant has its own name, reference hero with views, manifest, program
    versions (numbered per variant), builds and current version. Name, description and triangle budget stay on the
    asset.
  - Every existing asset gets one variant called "default" that owns its current concepts, programs and builds.
  - **Two picked heroes:** a variant has at most one reference hero. Picking a second hero for a variant asks the user
    to either replace the reference (the old hero is unpicked and its views stay as history) or start a new variant
    from that hero. Builds compare only against their own variant's reference hero, never "the newest picked hero".
- **Scenes.**
  - A placement can name a variant.
  - A version panel lists each asset and variant used in the scene, with one version choice that applies to all of its
    placements at once ("current" by default), and a "use current everywhere" action.
  - The save button is always enabled. It reads "Save and build" when there are unsaved edits and "Refresh" otherwise.
    Refresh rebuilds the scene with the chosen versions.
  - The scene page embeds the chat.
- **Blender file download.** Every build also saves a `.blend` file of the model. The asset page has a "Blender"
  download, next to Export, for a zip of the `.blend` and the current palette textures. The textures are linked by
  relative path, so palette edits never leave a stale `.blend`.
- **Delete a pack.** The pack list and the pack page can delete a pack after the user types its name. Deleting
  cancels the pack's running jobs and removes all of its content and chats. Knowledge notes stay.
- **Paged history.** Jobs, builds, program versions and the chat list are paged on the server. A long chat loads its
  newest turns first, with a button to load earlier ones. Asset parts and the report tables stay unpaged.
- **Normal repair and shading checks.**
  - Every build runs a normals pass before export: merge duplicate vertices, remove degenerate faces, make each closed
    piece's normals point outward. In smooth mode, normals are weighted by face area. The pass keeps the flat or
    smooth mode, hard edges and the program's `sharp()` and `smooth()` overrides.
  - The viewer can hide the baked vertex shade, so the user can tell a normals problem from a shade problem.
  - The build report counts what the pass fixed and lists what it could not fix: open edges, faces that still point
    inward, and non-planar faces left in place. The agent and the asset page can see these counts.

## Capabilities

### New Capabilities
- `asset-viewer`: the shared 3D viewer for builds and scenes: camera, overlays (wireframe, grid, axes, normals) and
  palette variant preview.
- `asset-variants`: variants of an asset, each with its own reference hero, manifest, program versions, builds and
  current version; what happens when a second hero is picked.

### Modified Capabilities
- `design-agent`: the per-pack chat becomes many chats, each with a page context. The user can stop a turn. The tools
  take an optional variant.
- `studio-ui`: new asset page layout with collapsible sections and the reference hero; chat embedded on the asset and
  scene pages; paged history lists; build comparison moves into a section.
- `asset-packs`: program versions, builds and the current version belong to a variant. Hero selection is one
  reference per variant. Packs can be deleted.
- `scenes`: placements choose a variant, versions are chosen per asset and variant, and the scene can always be rebuilt
  (Refresh).
- `part-modeling`: each build also saves a Blender file, downloadable with the current palette textures.
- `surface-shading`: the normals pass at export and its defect counts in the build report.

## Impact

- **Data (EF Core migration):**
  - new `AssetVariant` and `Chat` tables;
  - `VariantId` on `ConceptImage`, `Manifest`, `ProgramVersion` and `Build`;
  - `ChatId` on `Job`;
  - `CurrentProgramVersionId` and `Status` move from the asset to the variant (the asset shows the best status of its
    variants);
  - `Pack.AgentSessionId` moves into the pack's first chat;
  - existing rows are backfilled into a "default" variant per asset and one chat per pack.
- **API:**
  - variant endpoints;
  - `DELETE /packs/{id}`;
  - `GET /builds/{id}/blend` (a zip);
  - `Build.BlendFileId`, added in the same migration;
  - asset endpoints take an optional `variantId` (default variant when omitted);
  - chat endpoints move to `/chats` (list paged, create with page context, turns paged, stop);
  - history endpoints return `{ items, total }` pages;
  - `ScenePlacement` gains an optional `VariantId`, and `Scene` gains version choices per asset and variant.
- **MCP tools:**
  - variant tools (`list_variants`, `create_variant`);
  - optional `variantId` on manifest, program, build-report and job tools;
  - scene tools accept variant and version per placement.
- **Agent worker:** prompt composition with the context block; reports the session id as soon as the session starts,
  so a stopped turn keeps its session; ends the SDK query cleanly when the job is cancelled. `agent/CLAUDE.md` explains
  variants and the context block.
- **Geometry worker:** saves `model.blend` after the export and uploads it; normals pass in `export.py` (bmesh operations, the Weighted Normal modifier in smooth mode) and
  new defect counts in the report from `validate.py`.
- **UI:**
  - three.js replaces `<model-viewer>` (vendored in `wwwroot/lib` like model-viewer today);
  - new `ModelViewer` and paged-table components;
  - `ChatPanel` reworked and hosted in `MainLayout`;
  - asset and scene pages rebuilt.
- **Tests:** API tests for variants, chats, paging and scene versions; agent worker tests for the context block and
  for stopping; geometry tests for the normals pass; web smoke tests for the new pages.
