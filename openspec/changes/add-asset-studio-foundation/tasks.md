# Tasks

## 1. Repo conventions and configuration

- [ ] 1.1 Add root `CLAUDE.md` with dev rules: build ComfyUI workflows only through the `comfy` CLI against the container ComfyUI (never the GUI); minimal code, reuse, popular maintained libraries only; never commit host paths or tokens (placeholders like `<models-dir>`). Verify the file exists and contains no absolute host paths
- [ ] 1.2 Add `.data/` to `.gitignore`; verify `git check-ignore .data/x` matches
- [ ] 1.3 Remove the starter weather sample (API endpoint, `WeatherApiClient`, Weather/Counter pages); verify `dotnet build Slopoly.slnx` succeeds
- [ ] 1.4 Add AppHost parameters `comfyui-models-dir`, `data-dir` (default `.data`), `claude-oauth-token` (secret), `worker-key` (secret, generated); document the `dotnet user-secrets set` commands with placeholder values in `README.md`. Verify `aspire start` prompts for missing values in the dashboard

## 2. API data and files

- [ ] 2.1 Add EF Core SQLite to `Slopoly.ApiService` with the model from design §12 and an initial migration applied at startup, database under `<data-dir>`; verify the database file is created on first run
- [ ] 2.2 Implement file storage (`StoredFile`, upload/download endpoints, files under `<data-dir>/files`); verify with an API test that uploads and downloads the same bytes
- [ ] 2.3 Implement pack, style reference, asset and concept-selection endpoints (create/edit pack, upload/remove reference, pick/reject concept); verify with API tests covering the asset-packs scenarios
- [ ] 2.4 Implement manifest storage with parent validation, immutable program versions, builds and "set current version"; verify with API tests for unknown-parent rejection and rollback
- [ ] 2.5 Add the SignalR hub broadcasting entity-changed events; verify a test client receives an event when a pack is created

## 3. Job queue

- [ ] 3.1 Implement jobs: submit, claim by kinds (atomic conditional update), heartbeat returning `cancelRequested`, events, complete/fail, cancel, retry; worker endpoints require the `worker-key` header. Verify with API tests: kind filtering, cancel flag, retry, unauthorised claim rejected
- [ ] 3.2 Add the hosted service requeuing expired leases; verify with a test that an un-renewed claim returns to queued
- [ ] 3.3 Broadcast job state and events over the hub; verify in a test that a subscriber sees queued → running → succeeded

## 4. Shared Python worker client

- [ ] 4.1 Create `workers/slopoly_worker` (httpx, pydantic): claim loop, heartbeat task, event posting, file download/upload, cancellation as asyncio cancel, handler registry per kind; verify with pytest against a mocked API (respx) covering claim → complete and cancel mid-run
- [ ] 4.2 Document the worker protocol and how to add a handler in `workers/README.md`; verify the documented example handler runs in the test suite

## 5. ComfyUI container and image jobs

- [ ] 5.1 Create `containers/comfyui` Dockerfile (CUDA base, ComfyUI and custom nodes pinned via comfy-cli, slopoly_worker, `--listen`, `--reserve-vram` from config) and wire it in the AppHost with GPU access, writable bind mount of `comfyui-models-dir`, localhost port; verify the container starts and `comfy` CLI on the host can list nodes from it
- [ ] 5.2 Implement the comfy job handler: load `comfyui/workflows/<name>.json`, fill `in:*` titled nodes, stage input images into ComfyUI's input folder (with placeholder + `use_reference_n=false` for empty slots), submit, stream progress, upload `out:*` outputs, interrupt on cancel, report missing-model errors clearly; verify with pytest using a recorded ComfyUI API fixture
- [ ] 5.3 Build `style-anchor` workflow with the `comfy` CLI (FLUX.2 klein 4B, 3 reference slots); verify a job produces a scene image stored as a pack concept
- [ ] 5.4 Build `turnaround` workflow (3:1 front/side/top sheet, anchor as reference 1); handler records the three view regions; verify a cart job stores an image with three regions
- [ ] 5.5 Choose the segmentation node pack (resolve design open question), build `segment-parts`; handler runs per view region, stores mask PNGs with bbox/area and lists missing parts; verify on the cart turnaround that wheel/handle/bed masks are produced and a nonsense part is reported missing
- [ ] 5.6 Document required model files (names and `<models-dir>` subfolders) and download commands in `comfyui/README.md`; verify every model referenced by the three workflows is listed

## 6. Geometry worker

- [ ] 6.1 Create `containers/geometry` Dockerfile (Python version matching the pinned `bpy` wheel, manifold3d, trimesh, numpy, pillow, slopoly_worker) and wire it in the AppHost; verify the worker registers and claims a no-op build
- [ ] 6.2 Implement `slopoly_model` primitives and ops (`box`, `prism(n)`, `cone(n)`, `ngon`, `sweep`, `extrude`, `inset`, `bevel`, manifold3d `boolean`), `part` with parent, mirror, joint/pivot, sockets, and `instance`; verify with pytest: 8-sided wheel has 8 rim faces, mirrored part equals X-negated vertices, 30 instances from 3 definitions share 3 meshes
- [ ] 6.3 Implement validators (pairwise intersection volume, contact tolerance, connectivity from root, polygon budget) producing the JSON report; verify with pytest fixtures for overlapping, floating and clean assemblies
- [ ] 6.4 Implement silhouette scoring (orthographic projection, pillow fill, per-view bbox alignment, per-part IoU and signed size/centre errors); verify with pytest that a deliberately narrow wheel yields negative width error
- [ ] 6.5 Implement the build handler: run program in a subprocess with timeout, map tracebacks to program line, validate, score against picked turnaround masks, export GLB (Y-up, metres, pivots, instances, socket empties), upload GLB + report; verify the cart sample program produces a GLB whose axle node origin lies on the axle axis
- [ ] 6.6 Write the `slopoly_model` API reference used by the agent (`agent/docs/slopoly_model.md`); verify every public function is documented, checked by a pytest that compares exported names with the doc

## 7. MCP server

- [ ] 7.1 Add the official MCP C# SDK to the API with streamable HTTP behind `worker-key`; implement tools from design §10 as thin wrappers over existing services; verify with an API test that lists tools and calls `create_asset`, and that a UI hub event follows
- [ ] 7.2 Ensure tool results carry ids/numbers only and `view_image` alone returns image content; verify with a test asserting no base64 payloads in `get_segmentation` and `get_build_report`

## 8. Design agent

- [ ] 8.1 Create `containers/agent` (Python, Claude Agent SDK, slopoly_worker, named volume for Claude session data, `agent/` mounted read-only as cwd) and wire it in the AppHost with `CLAUDE_CODE_OAUTH_TOKEN` from the secret parameter; verify the worker registers
- [ ] 8.2 Implement the `agent-turn` handler: resume the pack's session, allow only the Slopoly MCP tools, enforce max turns, forward streamed messages as job events, persist the session id, map 401 to a distinct `auth` error; verify with pytest using a stubbed SDK client
- [ ] 8.3 Write `agent/CLAUDE.md`: pipeline stages (style → anchor → user approval → turnaround → approval → segmentation → manifest → program → build/iterate), use only non-rejected concepts, avoid `view_image` unless necessary, stop and report blockers; verify a real turn with a brief updates the pack style and starts a style-anchor job
- [ ] 8.4 Document authorisation (`claude setup-token`, set the parameter, re-auth on error) in `README.md`; verify by following the steps on a fresh user-secrets store

## 9. Web UI

- [ ] 9.1 Add MudBlazor, layout and navigation, typed API clients and SignalR client in `Slopoly.Web`; verify the app renders with MudBlazor layout and live-updates when a pack is created through the API
- [ ] 9.2 Packs list and Pack page: edit instructions/style text, upload/remove style references, concept gallery with pick/reject and "more variants", assets list, jobs list with cancel/retry; verify through the browser against the asset-packs and generation-jobs scenarios
- [ ] 9.3 Chat drawer per pack streaming agent events (text, tool activity, errors, auth error with re-auth steps), history reload; verify by sending a message and reloading the page
- [ ] 9.4 Asset page: manifest, program versions with "set current", builds with validator and score tables, `<model-viewer>` (vendored pinned file) with part names; verify a cart GLB loads and rotates in the viewer

## 10. End-to-end

- [ ] 10.1 Run the cart scenario from the design-agent spec on the target machine: brief → anchor approval → cart turnaround approval → segmentation → manifest → iterate to a validated build; record outcome, timings and blockers in the change's notes; verify the final GLB is viewable and its axle/wheel node spins in place
- [ ] 10.2 Run `git grep` for the developer's host path fragments and token prefixes; verify no matches in tracked files

## Workflow follow-up

- Archive the change after the cart run is reviewed.
