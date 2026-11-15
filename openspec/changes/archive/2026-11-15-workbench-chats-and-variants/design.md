## Context

Current state, as found in the code:

- **Viewer.** `AssetPage.razor` and `ScenePage.razor` use `<model-viewer>` 4.4.0, vendored in `wwwroot/lib`.
  `wwwroot/js/viewer.js` swaps the palette texture through model-viewer's material API. model-viewer hides its
  three.js scene, so it cannot draw a wireframe, a grid, axes or normal helpers.
- **Chat.**
  - There is one chat per pack: `Pack.AgentSessionId`, `POST/GET /api/packs/{id}/chat`, and `ChatPanel` in a drawer
    on `PackPage` only.
  - A turn is an `agent-turn` job whose inputs are `{message, sessionId}`. `agent_worker.py` prefixes `[Pack <id>]`
    and resumes the session. `AgentTurnHandler` in `ResultHandlers.cs` saves the session id, but only when the turn
    succeeds.
  - Cancel exists for every job (`POST /jobs/{id}/cancel`, broadcast on `job-control`; `slopoly_worker` cancels the
    handler task). A cancelled turn therefore never stores its session id, so the next turn resumes the session from
    before the cancelled turn and loses everything that turn did.
- **Heroes and builds.** `GenerationService.BuildInputsAsync` takes the newest picked hero of the asset. With two
  picked heroes, the older one is ignored without telling anyone. `CurrentProgramVersionId` and `Status` live on
  `Asset`. Program numbers are unique per `(AssetId, Number)`. `Manifest` is keyed by `AssetId`.
- **History lists.**
  - `JobList` loads `Take(200)` and the asset page loads every build and program version.
  - Asset and scene pages use `MudSimpleTable`.
  - `/jobs` also serves the scene page's "is it building" check.
- **Normals.**
  - `export.py` sets flat or smooth shading, the angle rule and the edge overrides.
  - Some shape constructors call `bmesh.ops.recalc_face_normals`, but not all of them, and nothing runs on the final
    part mesh.
  - `validate.py` checks solidity through manifold3d but reports nothing about normals.
  - A face whose corners do not lie in one plane is split into two triangles on export. In flat shading the two
    triangles get different normals, which shows as a crease.
  - Mirrored parts are nodes with a negative scale; glTF viewers flip their winding, which is correct.

Constraints: minimal code; popular libraries only; everything stays local (no CDN at runtime); the repo is public.

## Goals / Non-Goals

**Goals:**
- One viewer component used by the asset and scene pages, with diagnostic overlays.
- Chats as first-class records: many per pack, optionally without a pack, each with a page context. Stopping a turn
  keeps its session.
- Variants that move ownership of heroes, manifest, versions and builds off the asset, with a lossless data migration.
- Server-side paging on the long history lists, through one shared pattern.
- A normals pass at export that repairs what it safely can and reports the rest.

**Non-Goals:**
- Editing geometry in the viewer, or a transform gizmo for scene placements.
- Per-variant triangle budgets or per-variant palettes (palette variants stay pack-wide and are a separate concept).
- Branching or merging chats, or carrying a summary from one chat into another.
- Paging the concept gallery or the knowledge list (not requested; they can adopt the same pattern later).
- Automatically fixing open meshes or bent faces; these are reported to the agent.

## Decisions

### D1. three.js viewer replaces model-viewer

- Vendor three.js r170 as ES modules in `wwwroot/lib/three-0.170.0/`: `three.module.min.js` plus the addons
  `OrbitControls`, `GLTFLoader`, `RoomEnvironment` and `VertexNormalsHelper`.
- A new module `wwwroot/js/viewer3d.js` exports `create(element, options)`, which returns a handle with `load(url)`,
  `setOverlays({wireframe, grid, axes, normals, shade})`, `setPalette(url)`, `resetView()` and `dispose()`. The
  overlays work as follows:
  - **Wireframe:** a `LineSegments(WireframeGeometry)` child for each mesh.
  - **Grid:** `GridHelper` with 1-metre cells, sized to the model.
  - **Axes:** `AxesHelper` at the origin.
  - **Normals:** a `VertexNormalsHelper` for each mesh, with the line length set to 3 % of the bounding sphere.
  - **Shade:** hiding the baked shade sets `material.vertexColors = false`.
  - **Palette:** setting a palette replaces `material.map` with a nearest-filtered texture, which is what
    `setPalette` does today.
  - **Light:** a `RoomEnvironment` PMREM, close to model-viewer's neutral look.
- `Shared/ModelViewer.razor` loads the module through `IJSObjectReference` and holds the toolbar (MudToggleIconButtons
  for the overlays, plus reset view). It keeps the overlay choices in `localStorage` (read in try/catch). Its
  parameters are `Src`, `PaletteUrl` and `Height`, plus a `Toolbar` render fragment where pages add the palette choice
  and Export.
- `model-viewer` is removed from `App.razor` and from `wwwroot/lib`. `viewer.js` keeps only `scrollToEnd`.
- *Alternatives:*
  - Keep model-viewer and overlay a second canvas: model-viewer does not expose its camera to sync with.
  - Babylon.js has a built-in inspector, but it is much heavier.
  - three.js is what model-viewer already used inside, so the lighting stays familiar.

### D2. Chat records and context composed on the server

- New entity `Chat`:
  - `Id`, `PackId?`, `Title`, `SessionId?`;
  - `Context` (JSON `ChatContext`);
  - indexed `AssetId?`, `VariantId?` and `SceneId?`, copied from the context to find "the newest chat on this asset";
  - `CreatedAt` and `UpdatedAt`.
- `Job` gains an indexed `ChatId?`.
- `ChatContext` (Contracts) is a record:
  - `Page` (`home|pack|asset|scene|concept|knowledge`);
  - `PackId?`, `AssetId?`, `VariantId?`, `BuildId?`, `SceneId?`, `ConceptId?`;
  - `Tab?`, the pack tab.

  Pages publish their context to a scoped `PageContext` service in Slopoly.Web. `MainLayout`'s drawer and the
  embedded panels read it.
- API:
  - `GET /chats?packId&assetId&sceneId&skip&take` returns a page.
  - `POST /chats {context}` creates a chat. The title is set from the first message.
  - `GET /chats/{id}/turns?before&take` returns the newest turns first.
  - `POST /chats/{id}/messages {message, context}`.
  - `POST /chats/{id}/stop`.
  - The old `/packs/{id}/chat` routes are removed.
- `ChatPromptService` builds the prompt on the server, from the database, so names and states are authoritative:
  - The **first message** of a chat gets a `[Context]` block, built from the chat's stored context. It has one line
    per object, with name, id and key state: the pack's name and shading; the asset and variant with status and
    current version; the build with its program version, validation and mean object IoU; the scene with its
    placements, variants and versions; or the concept with its kind and selection.
  - **Every later message** gets one `[Viewing: …]` line built from the context sent with that message.
  - The job inputs keep the raw `message` for display, plus `prompt`, `sessionId` and `chatId`. `agent_worker.py`
    sends `prompt` as it is, falling back to `message`, and no longer adds `[Pack …]` itself.
- A chat with no pack submits its jobs with a null `PackId`. Live updates for such chats are matched by `ChatId`, so
  `ChatPanel` overrides the concern check and filters job events by chat id.
- *Alternative:* the UI sends a context text it composes itself. Rejected: names and states would then be duplicated
  in Blazor, and the agent could receive stale data.

### D3. Stopping keeps the session

- `agent_worker.py` streams `{kind: "session", sessionId}` as soon as the SDK's `init` message arrives.
- `JobEventApplier` gets a small hook: for `agent-turn` stream events of kind `session`, it writes the id to the
  chat's `SessionId`. The success handler keeps doing the same, which is harmless.
- `POST /chats/{id}/stop` cancels the chat's queued and running `agent-turn` jobs through `JobService.CancelAsync`.
- The worker already cancels the handler task. The query loop is wrapped in `contextlib.aclosing(query(...))`, so a
  cancel closes the SDK generator and ends the Claude Code subprocess right away. Claude Code writes the session file
  as the turn goes, so resuming after a stop includes the partial turn.
- The UI shows a Stop button while any turn of the chat is queued or running. A cancelled turn ends with a "stopped"
  note.

### D4. Variants own the modelling data; ids reused for the backfill

- New entity `AssetVariant`: `Id`, `AssetId`, `Name` (unique per asset), `Status`, `CurrentProgramVersionId?` and
  `CreatedAt`.
- `Asset` gains `DefaultVariantId`. It keeps `Status`, which is recomputed as the furthest status among the variants
  whenever a variant's status changes, so the Assets tab can keep filtering on it. `Asset.CurrentProgramVersionId` is
  dropped.
- `ConceptImage.VariantId?` is set for heroes and views; anchors have none. `ProgramVersion.VariantId` is added, with
  a unique index on `(VariantId, Number)`. `Build.VariantId` is added. The key of `Manifest` becomes `VariantId`.
- **Migration backfill without generating GUIDs in SQL:** each asset's default variant reuses the asset's id
  (`INSERT INTO AssetVariants SELECT Id AS Id, Id AS AssetId, 'default', Status, CurrentProgramVersionId, CreatedAt
  FROM Assets`). Then `UPDATE … SET VariantId = AssetId` runs for heroes and views, program versions, builds and
  manifests. In the same way, each pack's first chat reuses the pack id, with `SessionId = Pack.AgentSessionId`, and
  `UPDATE Jobs SET ChatId = PackId WHERE Kind = 'agent-turn'`. `Pack.AgentSessionId` is dropped. Ids stay globally
  unique because asset, variant, pack and chat ids are all v7 GUIDs from separate tables.
- API:
  - `GET/POST /assets/{id}/variants`;
  - `PATCH/DELETE /variants/{id}`, where the PATCH covers renaming and making a variant the default;
  - asset-scoped routes (`/assets/{id}/manifest|programs|builds|current-version`) take `?variantId=` and resolve a
    missing one to `DefaultVariantId` through a single helper, `StudioService.VariantOfAsync(assetId, variantId)`.
  This keeps the URLs and MCP tools backward compatible.
- `POST /assets/{id}/variants {name, fromVariantId? | fromHeroId?}` creates a variant:
  - With `fromVariantId`, it copies the manifest, and the source's current program becomes version 1.
  - With `fromHeroId`, it moves the hero and its views to the new variant and picks the hero.
- Hero selection is `PUT /concepts/{id}/selection {selection, onConflict?: "replace" | "newVariant", variantName?}`.
  Picking a hero whose variant already has a different picked hero, without `onConflict`, returns 409 with
  `code = "reference_exists"`. The UI catches that code and shows a two-button dialog, then sends the request again
  with the choice. MCP has no pick tool (the agent asks the user, per "Agent respects user selection"), so the agent
  cannot hit this case.
- `BuildInputsAsync(variant, version)` takes the variant's picked hero. Without one, the comparison is skipped and
  the report says `"no reference hero for this variant"`.
- Deleting a variant is refused, with the scene names, while any scene placement or version choice references it. It
  is also refused when it is the asset's only variant. Otherwise the variant's rows are removed by the existing
  cascade code.
- The `hero` workflow input and `start_job` gain `variantId?`. The views and segment jobs inherit the variant from the
  hero.
- MCP:
  - new tools `list_variants(assetId)`, `create_variant(assetId, name, fromVariantId?)` and
    `update_variant(variantId, name?, makeDefault?)`;
  - `variantId?` is added to `save_manifest`, `submit_program` and `get_build_report` (the build tells its variant
    anyway);
  - `list_concepts` returns `variantId`.
- The word "variant" alone means an asset variant. Palette variants are always called "palette variants" in the UI.

### D5. Scene version choices

- `ScenePlacement` gains `VariantId?`; null means the asset's default variant.
- `Scene` gains `Versions: List<SceneVersion(AssetId, VariantId, ProgramVersionId?)>` as a JSON column; a null or
  missing entry means the current version.
- `SaveSceneAsync` resolves each placement to `(variant, version)`, then to that version's latest build that has a
  model. If there is none, the error names the asset, the variant and the version.
- The scene page:
  - a "Versions" section lists the distinct `(asset, variant)` pairs of the rows, each with a version select
    (`current`, then v-numbers, newest first);
  - a "Use current everywhere" button clears the choices;
  - the button label is `Dirty ? "Save and build" : "Refresh"`, and it is always enabled. Refresh posts the unchanged
    scene, which rebuilds it.
- `save_scene` accepts `variantId` per placement and an optional `versions` list.

### D6. One paging pattern

- Contracts: `record Page<T>(List<T> Items, int Total)`.
- The history endpoints take `skip` and `take` (default 25, maximum 200) and return a `Page<T>`:
  - `/packs/{id}/jobs`;
  - `/assets/{id}/builds` and `/assets/{id}/programs`, both with `?variantId`;
  - `/chats`.
- The UI uses MudBlazor's `MudTable` with `ServerData`, which gives page controls and page sizes 10, 25 and 50. A
  live event calls `table.ReloadServerData()` and does not refetch the whole list. `JobList`, the builds section and
  the program versions section use it.
- The asset page also needs the selected build and the current program, which may not be on the current page. It
  fetches them by id (`GET /builds/{id}`, `GET /programs/{id}`, both new).
- The un-paged `/jobs` query used by the scene page stays as it is, with its `Take(100)`.
- Chat turns use `before`/`take` (keyset paging on `CreatedAt`), because chats load newest first and grow at the end.

### D7. Asset page layout

- **Top row:**
  - `MudGrid` with the viewer at `lg=7` (with the toolbar slot holding the build chip, the palette-variant select and
    Export) and the embedded `ChatPanel` at `lg=5`, the same height as the viewer.
  - Above both: the title, the status chip, a variant `MudSelect` (with "New variant…", rename and delete), and Edit
    and Delete.
  - The selected variant goes in the query string (`?variant=<id>`).
- **Below:** `MudExpansionPanels` with `MultiExpansion`, in this order:
  1. Reference (open by default);
  2. Build comparison;
  3. Builds (paged);
  4. Build report (the existing `JsonTable`s plus the new shading section);
  5. Manifest;
  6. Program versions (paged);
  7. New program version.

  The panels contain the existing markup, moved as it is.
- **Context:** the page publishes
  `ChatContext(Page: "asset", PackId, AssetId, VariantId, BuildId: selected build)` whenever the variant or the build
  changes.
- **Scene page:** the viewer on the left and the chat on the right, with the placements, versions and report below in
  panels.

### D8. Normals pass in the geometry worker

In `export.py`, just after `shape.bm` is copied for each mesh and before `to_mesh`:

1. **Repair.** A new `normals.repair(bm)` returns counts:
   - `bmesh.ops.remove_doubles(dist=1e-4)` gives the merged vertex count;
   - `bmesh.ops.dissolve_degenerate(dist=1e-6)` gives the removed face count;
   - `bmesh.ops.recalc_face_normals` runs; the flipped count is the faces whose normal changed sign.
   Face tags (palette roles) are face attributes and the edge flags are edge layers, so both survive.
2. **Smooth mode.** After `_shade`, a temporary object gets a `WEIGHTED_NORMAL` modifier (`mode='FACE_AREA'`,
   `keep_sharp=True`). The evaluated mesh replaces the mesh through `bpy.data.meshes.new_from_object`. The exporter
   writes the custom split normals.
3. **Check.** `normals.defects(bm)` runs on each part's mesh and returns:
   - boundary (open) edges;
   - closed pieces whose signed volume is still negative ("inward");
   - faces of four or more corners whose triangle normals differ by more than 5° ("bent").

The report gains `shading: {merged, removed, flipped, parts: [{part, openEdges, inward, bent}]}`. The asset page shows
it as a `JsonTable` in the build report section, and `get_build_report` returns it, so the agent sees it.
`agent/CLAUDE.md` gets a short rule: fix open edges with solidify or a closed primitive, and fix bent faces by
triangulating or flattening.

*Alternative:* doing the repair through trimesh (`fix_normals`). Rejected: it runs on the exported triangles, would
lose the Blender edge flags, and duplicates what bmesh already does where the mesh lives.

### D9. Pack deletion

- `StudioService.DeletePackAsync(id)` runs in this order:
  1. Cancel the pack's queued and running jobs through `JobService.CancelAsync`. This broadcasts the cancel, so workers
     discard their results, and the result handlers ignore jobs that are already cancelled.
  2. Delete the rows with `ExecuteDeleteAsync`, children first, in one transaction: part masks, concepts, builds,
     program versions, manifests, variants, assets, scenes, palette variant colours, palette variants, palette
     entries, style references, job events, jobs, chats, and finally the pack.
  3. Send `notifier.Changed<Pack>`.
- `DELETE /packs/{id}` maps to it.
- **UI:** a Delete action on the pack page header and in the pack list's row menu. It opens a MudDialog with a text
  field, and its Delete button is enabled only when the field equals the pack name. After deleting, the user is taken
  to `/`.
- **Files:** stored files are left on disk, as asset and concept deletes already do. A sweep of files that nothing
  references is out of scope.
- **Results that arrive late** for a deleted pack's jobs find no job row. The result handler already treats a missing
  or cancelled job as "ignore", and a test covers this.

### D10. Blender file per build

- **Saving.** At the end of `export()`, still in the same Blender session (`runner.py` already builds into an empty
  factory scene), the build:
  - sets the scene units to metric with a length scale of 1;
  - points the palette image at `//palette.png` (`image.unpack(method='REMOVE')`, then a relative `filepath`), so it
    is not packed;
  - saves with `bpy.ops.wm.save_as_mainfile(filepath=out/"model.blend", compress=True, relative_remap=True)`.

  The file keeps:
  - the objects in Blender space (Z up), since `TO_BLENDER` is applied before export;
  - the `sharp_edge` and palette-role attributes;
  - joints as custom properties;
  - socket empties;
  - the vertex-shade multiply node in the material.

  The GLB is exported before the image path changes, so the GLB still embeds the palette.
- **Uploading.** The geometry worker uploads `model.blend`, and `outputs.blendFileId` becomes `Build.BlendFileId`
  (nullable; older builds have none).
- **Download.** `GET /builds/{id}/blend` zips:
  - `<asset>[-<variant>]-v<n>.blend`;
  - `palette.png`, the pack's current main texture;
  - `palette_<name>.png` for each rendered palette variant.

  This reuses the zip code of `/builds/{id}/export`, which is pulled into one helper. With no `BlendFileId`, it
  answers 409 "rebuild this version to get a Blender file".
- **UI:** a "Blender" button next to Export in the viewer toolbar. It is disabled, with that tooltip, when the build
  has no Blender file.
- *Alternative:* pack the palette into the `.blend` and re-pack it on every palette render. Rejected: palette-render
  would need a Blender session for each build, while it does GLBs in pure Python today. A relative texture also lets
  the user switch to a palette variant by swapping one image. Scenes get no Blender file in this change.

## Risks / Trade-offs

- **The Blender file opens only in the container's Blender version or newer.** → The asset page tooltip and the README
  name the Blender version that the geometry image pins.

- **Data migration touches most tables.** → The id-reuse backfill is plain SQL, and EF generates the schema part. A
  test opens a copy of a database migrated from `PackShading` and checks the counts and links. Back up `<data-dir>`
  before the first start (README note).
- **`remove_doubles` may weld separate pieces that touch at a point** (two boxes sharing a corner), making them
  non-manifold at that vertex. → The distance is tiny (0.1 mm), the merge is limited to one part's mesh, and anything
  left non-manifold shows up in `openEdges`.
- **The Weighted Normal modifier depends on the Blender version** (custom normals since 4.1). → The geometry container
  pins its Blender version, and a geometry test asserts that a bevelled box's large face has uniform normals.
- **The three.js swap could change how models look** compared with model-viewer (exposure, environment). → Use
  `RoomEnvironment` with ACES tone mapping and exposure 1, and check against the cart in the web smoke test
  screenshot.
- **Several chats may queue agent turns at once.** The agent worker runs one turn at a time, so a turn in another
  chat waits in the queue. → The chat shows "queued", and Stop also clears queued turns.
- **The context block costs tokens on every first message.** → One line per object, ids and numbers only, no report
  bodies (the agent uses tools for those).
- **The word "variant" now has two meanings** (asset variant and palette variant). → The UI always says "palette
  variant" for palettes, and the MCP tools say `palette` in their names.
