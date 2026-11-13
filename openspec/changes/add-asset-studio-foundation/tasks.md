# Tasks

## 1. Repo conventions and configuration

- [ ] 1.1 Add root `CLAUDE.md` with dev rules: build ComfyUI workflows only through the `comfy` CLI against the container ComfyUI (never the GUI); minimal code, reuse, popular maintained libraries only; never commit host paths or tokens (placeholders like `<models-dir>`); the app needs only Docker, .NET and Aspire on the host, and the developer's host Python/`comfy` CLI are allowed for development only. Verify the file exists and contains no absolute host paths
- [ ] 1.2 Add `.data/` to `.gitignore`; verify `git check-ignore .data/x` matches
- [ ] 1.3 Remove the starter weather sample (API endpoint, `WeatherApiClient`, Weather/Counter pages); verify `dotnet build Slopoly.slnx` succeeds
- [ ] 1.4 Add the RabbitMQ resource (Aspire hosting integration, management plugin, mounted `rabbitmq.conf` raising `consumer_timeout`) to the AppHost; verify the broker starts and its management UI opens from the dashboard
- [ ] 1.5 Add AppHost parameters `comfyui-models-dir`, `data-dir` (default `.data`), `claude-oauth-token` (secret), `worker-key` (secret, generated); document the `dotnet user-secrets set` commands with placeholder values in `README.md`. Verify `aspire start` prompts for missing values in the dashboard

## 2. API data and files

- [ ] 2.1 Add EF Core SQLite to `Slopoly.ApiService` with the model from design §12 and an initial migration applied at startup, database under `<data-dir>`; verify the database file is created on first run
- [ ] 2.2 Implement file storage (`StoredFile`, upload/download endpoints, files under `<data-dir>/files`); verify with an API test that uploads and downloads the same bytes
- [ ] 2.3 Implement pack, style reference, asset and concept-selection endpoints (create/edit pack, upload/remove reference, pick/reject concept); verify with API tests covering the asset-packs scenarios
- [ ] 2.4 Implement manifest storage with parent validation, immutable program versions, builds and "set current version"; verify with API tests for unknown-parent rejection and rollback
- [ ] 2.5 Add the SignalR hub broadcasting entity-changed events; verify a test client receives an event when a pack is created

## 3. Job queue

- [ ] 3.1 Add Aspire's RabbitMQ client integration to the API and declare the topology from design §2 (`jobs` direct exchange with a durable queue per kind, `job-events` topic exchange with the API's queue, `job-control` fanout); verify in an Aspire test that the queues and exchanges exist after start
- [ ] 3.2 Implement job submit (save row, then publish persistent message; on publish failure mark failed with "dispatch failed"), cancel (mark row, publish control message), retry (republish same id, new attempt) and `GET /jobs/{id}` state for workers; verify with API tests using the Aspire-started broker
- [ ] 3.3 Implement the API's background consumer of `job-events`: update state and attempt count, store `JobEvent`s, accept only the first `succeeded` per job, ignore results of cancelled jobs, broadcast on SignalR; verify with a test that publishes started → progress → succeeded and a subscriber sees each state

## 4. Shared Python worker package

- [ ] 4.1 Add a container-based test runner (a test image or `docker compose run` setup with the source mounted read-only, plus an Aspire resource command to run it) so all Python tests run without host Python; verify a placeholder `pytest` run passes through it
- [ ] 4.2 Create `workers/slopoly_worker` (aio-pika, httpx, pydantic): consume configured kinds with manual acks and `prefetch=1`, skip jobs whose API state is cancelled, publish events, ack after the final event, listen on a per-worker `job-control` queue and cancel the running handler, enforce the attempt cap, file download/upload, handler registry per kind; verify with pytest run inside a container against a RabbitMQ test container: dispatch → succeeded, cancel mid-run, cancel before start, redelivery after the consumer drops without ack
- [ ] 4.3 Document the message contract (exchanges, queues, event types, cancel, attempt cap) and how to add a handler in `workers/README.md`; verify the documented example handler runs in the test suite

## 5. ComfyUI container and image jobs

- [ ] 5.1 Create `containers/comfyui` Dockerfile (CUDA base, ComfyUI and custom nodes pinned via comfy-cli, slopoly_worker, `--listen`, `--reserve-vram` from config) and wire it in the AppHost with GPU access, writable bind mount of `comfyui-models-dir`, localhost port; verify the container starts and `comfy` CLI on the host can list nodes from it
- [ ] 5.2 Implement the comfy job handler: load `comfyui/workflows/<name>.json`, fill `in:*` titled nodes, stage input images into ComfyUI's input folder (with placeholder + `use_reference_n=false` for empty slots), submit, stream progress, upload `out:*` outputs, interrupt on cancel, report missing-model errors clearly; verify with pytest (in container) using a recorded ComfyUI API fixture
- [ ] 5.3 Build `style-anchor` workflow with the `comfy` CLI (FLUX.2 klein 4B, 3 reference slots); verify a job produces a scene image stored as a pack concept
- [ ] 5.4 Build `turnaround` workflow (3:1 front/side/top sheet, anchor as reference 1); handler records the three view regions; verify a cart job stores an image with three regions
- [ ] 5.5 Choose the segmentation node pack (resolve design open question), build `segment-parts`; handler runs per view region, stores mask PNGs with bbox/area, measures each mask's dominant colours (Lab k-means, k ≤ 4, clusters < 5 % dropped) and lists missing parts; verify on the cart turnaround that wheel/handle/bed masks are produced a nonsense part is reported missing, and each found part has colours with coverage
- [ ] 5.6 Document required model files (names and `<models-dir>` subfolders) and download commands in `comfyui/README.md`; verify every model referenced by the three workflows is listed

## 6. Geometry worker

- [ ] 6.1 Create `containers/geometry` Dockerfile (Python version matching the pinned `bpy` wheel, manifold3d, trimesh, numpy, pillow, slopoly_worker) and wire it in the AppHost; verify the worker connects to the broker and completes a no-op build job
- [ ] 6.2 Implement `slopoly_model` primitives and ops (`box`, `prism(n)`, `cone(n)`, `ngon`, `sweep`, `extrude`, `inset`, `bevel`, manifold3d `boolean`), `part` with parent, mirror, joint/pivot, sockets, and `instance`; verify with pytest (in container): 8-sided wheel has 8 rim faces, mirrored part equals X-negated vertices, 30 instances from 3 definitions share 3 meshes
- [ ] 6.3 Implement validators (pairwise intersection volume, contact tolerance, connectivity from root, polygon budget) producing the JSON report; verify with pytest (in container) fixtures for overlapping, floating and clean assemblies
- [ ] 6.4 Implement silhouette scoring (orthographic projection, pillow fill, per-view bbox alignment, per-part IoU and signed size/centre errors); verify with pytest (in container) that a deliberately narrow wheel yields negative width error
- [ ] 6.5 Implement the build handler: run program in a subprocess with timeout, map tracebacks to program line, validate, score against picked turnaround masks, export GLB (Y-up, metres, pivots, instances, socket empties), upload GLB + report; verify the cart sample program produces a GLB whose axle node origin lies on the axle axis
- [ ] 6.6 Write the `slopoly_model` API reference used by the agent (`agent/docs/slopoly_model.md`); verify every public function is documented, checked by a pytest that compares exported names with the doc

## 7. Palette

- [ ] 7.1 Implement `slopoly_model.palette`: fixed slot layout (8×8 px solid cells in the top half, 4 px gradient strips in the bottom half of 256×256), texture rendering with Pillow, UV assignment for solid and gradient tags with half-pixel inset; verify with pytest (in container) that a slot's rectangle never changes when entries are added and sampled UVs land inside the right cell/strip
- [ ] 7.2 Add material tags to `slopoly_model` (part tag, named face groups from ops, inheritance, unknown-role and untagged-part failures) and write palette UVs plus one shared material into the GLB; verify with pytest (in container) on the cart sample: bed faces sample only the "cart wood" cell and a gradient part's low/high vertices sample strip start/end
- [ ] 7.3 Add colour likeness (CIEDE2000 between tagged main colour and mask dominant colour) to the build report; verify with pytest (in container) that a wheel tagged with a green role over a brown mask is flagged
- [ ] 7.4 Add palette data to the API (`PaletteEntry` with slot assigned once, `PaletteVariant`, `PaletteVariantColor` with fallback to main, unique roles, deletion refused while used by builds) with REST endpoints; verify with API tests for duplicate role, used-entry deletion and variant fallback for a new role
- [ ] 7.5 Implement the `palette-render` job (geometry worker): render main and variant textures, re-embed the main texture into the pack's current build GLBs without rerunning programs; API marks textures stale on colour edits and debounces the job; verify with an integration test that recolouring an entry changes the GLB's embedded image while its mesh data is byte-identical
- [ ] 7.6 Add palette MCP tools (`get_part_colors`, `get_palette`, `upsert_palette_entries`, `upsert_palette_variant`), reading main colours only for modelling tools; verify with an API test that `get_build_report` and scoring ignore variant colours
- [ ] 7.7 Exports embed the main texture and add `palette_<variant>.png` per variant; verify the export download contains one PNG per variant with the same dimensions as the main texture

## 8. MCP server

- [ ] 8.1 Add the official MCP C# SDK to the API with streamable HTTP behind `worker-key`; implement tools from design §10 as thin wrappers over existing services; verify with an API test that lists tools and calls `create_asset`, and that a UI hub event follows
- [ ] 8.2 Ensure tool results carry ids/numbers only and `view_image` alone returns image content; verify with a test asserting no base64 payloads in `get_segmentation` and `get_build_report`

## 9. Design agent

- [ ] 9.1 Create `containers/agent` (Python, Claude Agent SDK, slopoly_worker, named volume for Claude session data, `agent/` mounted read-only as cwd) and wire it in the AppHost with `CLAUDE_CODE_OAUTH_TOKEN` from the secret parameter; verify the worker connects and consumes `jobs.agent-turn`
- [ ] 9.2 Implement the `agent-turn` handler: resume the pack's session, allow only the Slopoly MCP tools, enforce max turns, forward streamed messages as job events, persist the session id, map 401 to a distinct `auth` error; verify with pytest (in container) using a stubbed SDK client
- [ ] 9.3 Write `agent/CLAUDE.md`: pipeline stages (style → anchor → user approval → turnaround → approval → segmentation → palette entries from measured colours → manifest → program → build/iterate), role-naming rule for palette entries (usage by default; a colour name only when the colour stays the same in every palette), variants only on request and never used for modelling, use only non-rejected concepts, avoid `view_image` unless necessary, stop and report blockers; verify a real turn with a brief updates the pack style and starts a style-anchor job
- [ ] 9.4 Document authorisation (`claude setup-token`, set the parameter, re-auth on error) in `README.md`; verify by following the steps on a fresh user-secrets store

## 10. Web UI

- [ ] 10.1 Add MudBlazor, layout and navigation, typed API clients and SignalR client in `Slopoly.Web`; verify the app renders with MudBlazor layout and live-updates when a pack is created through the API
- [ ] 10.2 Packs list and Pack page: edit instructions/style text, upload/remove style references, concept gallery with pick/reject and "more variants", assets list, jobs list with cancel/retry; verify through the browser against the asset-packs and generation-jobs scenarios
- [ ] 10.3 Palette editor on the Pack page: MudBlazor colour pickers per role, role-naming hint (usage by default; colour names only for colours fixed across palettes), add solid/gradient entries, "used by" list blocking deletion, variant list with create/edit; verify through the browser against the surface-palette scenarios
- [ ] 10.4 Chat drawer per pack streaming agent events (text, tool activity, errors, auth error with re-auth steps), history reload; verify by sending a message and reloading the page
- [ ] 10.5 Asset page: manifest, program versions with "set current", builds with validator and score tables, `<model-viewer>` (vendored pinned file) with part names and a palette variant selector that swaps the base-colour texture client-side; verify a cart GLB loads and rotates in the viewer and switching to a variant recolours it without a job

## 11. End-to-end

- [ ] 11.1 Run the cart scenario from the design-agent spec on the target machine: brief → anchor approval → cart turnaround approval → segmentation → manifest → iterate to a validated build; record outcome, timings and blockers in the change's notes; verify the final GLB is viewable, palette-coloured with role-named entries, and its axle/wheel node spins in place; then create an "autumn" variant through the chat and recolour one main entry in the UI, verifying both without a rebuild
- [ ] 11.2 Run `git grep` for the developer's host path fragments and token prefixes; verify no matches in tracked files

## Workflow follow-up

- Archive the change after the cart run is reviewed.
