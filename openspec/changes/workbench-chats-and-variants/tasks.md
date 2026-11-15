# Tasks

## 1. Data model and migration

- [ ] 1.1 Contracts: add `AssetVariant`, `Chat`, `ChatContext`, `SceneVersion` and `Page<T>`. Add `VariantId` to
  `ConceptImage`, `ProgramVersion`, `Build` and `Manifest` (the new key), `ChatId` to `Job`, `DefaultVariantId` to
  `Asset` and `VariantId` to `ScenePlacement`, and `Versions` to `Scene`. Remove `Asset.CurrentProgramVersionId` and
  `Pack.AgentSessionId`. Verify: `dotnet build` succeeds.
- [ ] 1.2 `SlopolyDb`: add the indexes (unique `(VariantId, Number)`; `Chat.AssetId`, `SceneId` and `PackId`;
  `Job.ChatId`) and the JSON columns (`Chat.Context`, `Scene.Versions`). Generate the EF migration `VariantsAndChats`.
  Add the SQL backfill from design D4: default variant id = asset id, first chat id = pack id with the pack's session,
  agent-turn jobs get `ChatId = PackId`. Verify: a migration test starts from a database at `PackShading` with an
  asset, two program versions, a build, a hero with views, a manifest and three chat turns. After migrating, each row
  links to the default variant or chat, and the session id has moved.

## 2. Variants in the API

- [ ] 2.1 `StudioService.VariantOfAsync(assetId, variantId?)`, plus the variant CRUD: create (empty, from a variant,
  from a hero), rename, make default, and delete (refused for the only variant or one used in a scene, naming the
  scenes). Asset status is recomputed from the variants. New assets get a "default" variant. Verify: API tests for
  each scenario in `asset-variants`.
- [ ] 2.2 Asset routes (`manifest`, `programs`, `builds`, `current-version`) take `?variantId`. Program numbering is
  per variant. `GenerationService.BuildInputsAsync` uses the variant's reference hero, and the report says
  "no reference hero for this variant" when it has none. The hero, views and segment jobs carry or inherit
  `variantId`. Verify: a test where two variants with different heroes get builds scored against their own views,
  and a test of numbering per variant.
- [ ] 2.3 Hero selection with `onConflict` (`replace` or `newVariant`). Without a choice, a conflicting pick returns
  409 `reference_exists`. Verify: API tests for replace, new variant and refusal; the old hero keeps its views after a
  replace.
- [ ] 2.4 MCP: add `list_variants`, `create_variant` and `update_variant`. Add `variantId` to `save_manifest`,
  `submit_program`, `get_build_report` and `start_job` (hero), and return it from `list_concepts`. Verify: extend
  `McpToolsTests`; a program submitted with a variant leaves the default variant unchanged.

## 3. Scenes

- [ ] 3.1 `SaveSceneAsync` resolves each placement's variant and version (from `Scene.Versions`, or the current
  version) to the latest build that has a model. The error names the asset, the variant and the version. `save_scene`
  accepts `variantId` per placement and `versions`. Verify: API tests for "older carts everywhere", "two cart
  variants" and "version without a build".
- [ ] 3.2 A scene save with unchanged content still queues a build (Refresh). Verify: an API test where PUT of an
  identical scene creates a new scene job.

## 4. Paging

- [ ] 4.1 `skip` and `take` (default 25, maximum 200) returning `Page<T>` on `/packs/{id}/jobs`,
  `/assets/{id}/builds`, `/assets/{id}/programs` and `/chats`. Add `GET /builds/{id}` and `GET /programs/{id}`.
  Verify: an API test with 60 jobs checks the totals, the order and the second page.
- [ ] 4.2 Shared paged-table use: `JobList`, the builds section and the program versions section use `MudTable` with
  `ServerData`, and live events reload the current page. Verify: the web smoke test opens the Jobs tab and sees the
  page controls and the total.

## 5. Chats and stopping

- [ ] 5.1 The `Chat` endpoints (list, create with context, paged turns via `before`/`take`, send message with
  context, stop). Remove `/packs/{id}/chat`. Verify: API tests: create a chat, send two messages, and list the turns
  newest first.
- [ ] 5.2 `ChatPromptService`: a `[Context]` block on the first message and a `[Viewing: …]` line on later ones,
  built from the database for the pack, asset, variant, build, scene, concept, knowledge and home pages. Job inputs
  are `{message, prompt, sessionId, chatId}`. Verify: unit-style API tests compare the prompt for an asset context
  with a build selected, and for a chat without a pack.
- [ ] 5.3 Agent worker: send `inputs.prompt` as it is, falling back to `message`. Stream `{kind: "session"}` on init.
  Wrap the query in `contextlib.aclosing`. Verify: `agent-tests`: the stub SDK sees the prompt unchanged, a session
  event is streamed first, and cancelling the task closes the generator.
- [ ] 5.4 `JobEventApplier` stores `session` stream events on the chat. Stop cancels the chat's queued and running
  turns. Verify: an API test where a cancelled turn, which had streamed a session event, leaves the chat with that
  session id, and the next message's job resumes it.
- [ ] 5.5 Update `agent/CLAUDE.md`: what the context block and the viewing line mean, how variants work (the default
  when omitted, never mixing a variant's versions), and the shading defects to fix (see 8.3). Verify: a review against
  design D2, D4 and D8.

## 6. Viewer

- [ ] 6.1 Vendor three.js r170 (`three.module.min.js`, `OrbitControls`, `GLTFLoader`, `RoomEnvironment`,
  `VertexNormalsHelper`) under `wwwroot/lib/three-0.170.0/` with its licence. Remove model-viewer from `App.razor` and
  `wwwroot/lib`. Verify: the app loads with no 404s in the browser console.
- [ ] 6.2 `wwwroot/js/viewer3d.js` (load, overlays, palette, reset view, dispose) and `Shared/ModelViewer.razor` (the
  toolbar toggles for wireframe, grid, axes, normals and baked shade, plus reset view, with choices kept in
  `localStorage` inside try/catch). Verify: in the running app, each toggle changes the cart view, and the choices
  survive switching builds and reloading the page.

## 7. Pages

- [ ] 7.1 `PageContext` scoped service. `MainLayout` gets an agent button and a drawer with the chat list,
  "New chat" and the current chat. Every page publishes its context. Verify: starting a chat from a concept page
  records that concept in the chat's context, which the API test checks.
- [ ] 7.2 `ChatPanel` rework: chat picker, "New chat", "Load earlier", a Stop button while a turn is queued or
  running, a "stopped" note, and job events filtered by chat id. Verify: in the running app, stopping a long turn
  ends it as cancelled and the next message continues.
- [ ] 7.3 Asset page rebuilt as in design D7: variant picker with new, rename and delete; viewer, chat, palette
  variant select and Export on top; expansion panels below with Reference open first. The second-hero dialog handles
  409 `reference_exists`. `?variant=` is in the URL. Verify: the web smoke test opens the cart and finds the viewer,
  the chat and the reference panel open, with the others collapsed.
- [ ] 7.4 Scene page: viewer and chat on top; a Versions section with a select per (asset, variant) and
  "Use current everywhere"; a variant column in the placements table; a save button that reads Save and build or
  Refresh and is always enabled. Verify: the web smoke test sees "Refresh" on an unchanged scene, and clicking it
  starts a scene job.

## 8. Normals pass

- [ ] 8.1 `geometry/slopoly_model/normals.py`: `repair(bm)` (remove_doubles 0.1 mm, dissolve_degenerate,
  recalc_face_normals) returns the merged, removed and flipped counts. `defects(bm)` returns the open edges, inward
  pieces and bent faces over 5°. Verify: `geometry-tests` cover an inward-wound extrusion (flipped and fixed), a
  single plane (open edges), a box with one raised corner (one bent face) and a clean box (all zero).
- [ ] 8.2 `export.py`: run the repair before `to_mesh`. In smooth mode, apply the `WEIGHTED_NORMAL` modifier
  (FACE_AREA, keep_sharp) through a temporary object. Edge flags and face tags are kept. Verify: `geometry-tests`: a
  smooth bevelled box's large face has uniform normals, the barrel's hard lid edge stays hard, and a mirrored part
  exports with outward normals.
- [ ] 8.3 Report `shading: {merged, removed, flipped, parts[]}` in the build report. Show it as a table in the asset
  page's build report section. Return it from `get_build_report`. Verify: `ShadingTests` reads the section from a
  build of a program with an open plane.

## 9. Pack deletion

- [ ] 9.1 `StudioService.DeletePackAsync` (cancel the pack's jobs, then delete its rows in one transaction, as in
  design D9) and `DELETE /packs/{id}`. Verify: an API test deletes a pack that has assets, variants, scenes, palette,
  chats and a running job. The job ends cancelled, no rows of the pack remain, knowledge notes remain, and a late
  result for the job is ignored.
- [ ] 9.2 Delete action on the pack page and in the pack list, with a dialog that requires typing the name and then
  goes to `/`. Verify: the web smoke test sees the dialog's Delete button disabled until the name matches.

## 10. Blender file

- [ ] 10.1 `export.py` sets metric units, links the palette image as `//palette.png` after the GLB export, and saves
  `model.blend`. The geometry worker uploads it as `blendFileId`. Verify: `geometry-tests` reopen the saved file with
  `bpy.ops.wm.open_mainfile` and find the cart's part objects, the hierarchy, the wheel joint property, the socket
  empties, a relative unpacked palette image, and the same triangle count as the GLB.
- [ ] 10.2 Add `Build.BlendFileId` (in the 1.2 migration) and store it in the build result handler. Add
  `GET /builds/{id}/blend` to zip the file with the current main and palette variant textures, sharing a zip helper
  with export; it answers 409 without a file. Verify: an API test checks the zip entry names, that `palette.png`
  equals the pack's current texture after a palette edit, and the 409 for an old build.
- [ ] 10.3 Blender download button in the asset page's viewer toolbar, disabled with a tooltip when the build has no
  file. Verify: the web smoke test finds the button enabled for a new build.

## 11. Wrap-up

- [ ] 11.1 README: back up `<data-dir>` before upgrading, and add short notes on variants and chats. Verify: no host
  paths or user names in the diff (`git diff | grep -i users` is empty).
- [ ] 11.2 Full run: `dotnet test Slopoly.Tests`, the `tests`, `geometry-tests` and `agent-tests` compose services,
  then `aspire start` and a manual pass over the asset and scene pages (overlays, chat context, stop, variants,
  Refresh, paging, pack delete, Blender download). Verify: all suites pass, and the manual pass is noted in the PR.
