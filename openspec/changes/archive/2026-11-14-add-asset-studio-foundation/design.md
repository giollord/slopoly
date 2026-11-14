# Design

## Context

- The repo is the Aspire 13.6 starter on .NET 11: `Slopoly.AppHost`, `Slopoly.ApiService`, `Slopoly.Web` (Blazor Server), `Slopoly.ServiceDefaults`, and `Slopoly.Tests` (NUnit with Aspire testing). It contains only sample weather code.
- **Target machine:** Windows 11, Docker Desktop on WSL 2, an RTX 4070 with 12 GB VRAM, 64 GB RAM. Only one large model fits on the GPU at a time.
- **The repo will be public.** Host paths and tokens may appear only as placeholders such as `<models-dir>` and `<data-dir>`.
- **Code rule:** minimal code, reuse over bespoke infrastructure, and only popular, maintained packages.
- **Host rule:** the app uses as little of the host as possible: Docker Desktop with GPU support, the .NET SDK and the Aspire CLI. All Python (ComfyUI, geometry, agent) runs in containers, and so do Python tests. The developer's host Python and `comfy` CLI may be used while developing, never as an app dependency.
- **Prior art from the author's video-bot project:**
  - FLUX.2 klein 4B, with separate reference images each chained through `ReferenceLatent` on both the positive and negative conditioning, kept a drawn style consistent on this GPU.
  - A `LoadImage` input needs a real file even when it is switched off, so empty reference slots get a placeholder image plus a boolean switch.
  - Workers that only open outbound connections made a remote GPU machine trivial.

See proposal.md for the motivation. The specs define the required behaviour.

## Goals / Non-Goals

**Goals:**
- One uniform worker protocol for every background process: ComfyUI jobs, geometry builds, and agent chat turns.
- The agent touches the app only through MCP tools, so the app's state stays authoritative and the UI stays live.
- A geometry core where topology, symmetry and pivots come from construction, not from reconstruction.

**Non-Goals:**
- Multi-user use, auth on the web UI, and hardening the API for exposure beyond localhost.
- Sandboxing agent-written programs beyond container isolation and a timeout. The programs come from the user's own agent.
- High-quality rendered previews. The browser's 3D viewer is the preview.

## Decisions

### 1. Topology

```
Browser --> webfrontend (Blazor Server + MudBlazor)
                 |  HTTP + SignalR client
                 v
            apiservice --- SQLite (EF Core) + <data-dir>/files
             |  REST: packs, files      publishes jobs + cancels
             |  MCP (HTTP): agent tools consumes job events
             |  SignalR hub: live UI           |
             ^                          +------v------+
             | HTTP (files, MCP)        |  rabbitmq   |
             |                          +------^------+
             |      AMQP (jobs, events, cancel)|
   outbound  +----------------+----------------+---------+
   +-------------+    +---------------+    +------------------+
   | comfyui     |    | geometry      |    | agent            |
   | ComfyUI     |    | bpy +         |    | Claude Agent SDK |
   | + worker    |    | slopoly_model |    | (Claude Code)    |
   | GPU, models |    | + worker      |    | + worker         |
   +-------------+    +---------------+    +------------------+
```

**Alternative:** the API calling ComfyUI directly. It is simpler today, but it breaks the planned "API in the cloud, GPU at home" setup, and it needs a second integration style for geometry and the agent.

### 2. Job dispatch through RabbitMQ; job state in SQLite
RabbitMQ runs as a container added with Aspire's hosting integration. The API uses Aspire's RabbitMQ client integration, which wraps the official `RabbitMQ.Client`. The broker carries messages, and SQLite stays the record of job state and history for the UI and the agent.

| Topology | Purpose |
|---|---|
| `jobs` direct exchange → durable queue per kind (`jobs.comfy`, `jobs.build`, `jobs.agent-turn`) | Dispatch. The API saves the `Job` row (queued) and then publishes `{jobId, kind, inputs}`. Messages are persistent |
| `job-events` topic exchange → API's queue | Workers publish `started`, `progress`, `stream` (agent output), `succeeded {outputs}` and `failed {error}`. The API's background consumer updates the row, stores `JobEvent`s and broadcasts them on SignalR |
| `job-control` fanout exchange → one exclusive auto-delete queue per worker | Cancel. The API publishes `{jobId}` and every worker hears it |

- **Delivery:** workers consume with manual acknowledgements and `prefetch=1`. A worker acknowledges only after posting its final event. If it dies or disconnects, RabbitMQ redelivers the message, and the API counts the attempt when it sees `started` again.
- **Redelivery limit:** jobs that keep failing are capped by a configurable maximum number of attempts, checked by the worker against the redelivery header and the job's attempt count. When the cap is reached, the job fails.
- **Cancel:**
  - *Queued job:* the API marks the row cancelled. When the message is delivered, the worker checks the job's state over HTTP, finds it cancelled, and acknowledges and skips it.
  - *Running job:* the worker cancels its running task. If the job ran to completion anyway, the API discards the late `succeeded`.
- **Retry:** the API republishes the job with the same id and a new attempt.
- **Long jobs:** the broker's `consumer_timeout` is raised (for example to 24 h) through a mounted `rabbitmq.conf`, so long agent turns or builds are not cut off. The spec's "Long job not cut off" scenario covers this.
- **Files** never go through the broker. Workers download inputs and upload outputs over HTTP before publishing `succeeded`.
- **Libraries:** MassTransit is avoided because version 9 moved to a commercial licence, and plain `RabbitMQ.Client` is enough for three queues and two exchanges.

**Alternative:** a hand-built queue in SQLite with HTTP claim, lease and heartbeat endpoints. It needs no extra container, but it re-implements redelivery and dispatch that a maintained broker already provides.

### 3. One shared Python worker package
`workers/slopoly_worker` is a small package installed in all three worker containers. It uses `aio-pika` (AMQP), `httpx` (files and job-state checks) and `pydantic` (messages), and handles:
- consuming from the configured kinds with `prefetch=1`, then running the handler for each message;
- publishing events;
- cancellation through the control queue, turned into an `asyncio` cancel of the running handler;
- file download and upload;
- the attempt cap.

Each container adds only a handler per job kind.

**GPU serialization:** the ComfyUI container is the only GPU consumer in this change, and its single consumer has `prefetch=1`, so only one GPU job runs at a time. ComfyUI starts with `--reserve-vram` (default 3 GB, configurable), because Windows holds GPU memory the container cannot see.

### 4. Configuration through Aspire parameters
| Parameter | Kind | Default |
|---|---|---|
| `comfyui-models-dir` | plain | none, so the dashboard prompts and can save it to user secrets |
| `data-dir` | plain | `<repo>/.data` (git-ignored) |
| `claude-oauth-token` | secret | none, so the dashboard prompts |
| `worker-key` | secret | generated (HTTP file and MCP access) |
| RabbitMQ credentials | secret | generated by the Aspire RabbitMQ integration |

- The models folder is bind-mounted **writable** at ComfyUI's models path, so a model downloaded by the agent or the developer lands in the shared host folder.
- The AppHost reads the folder values from configuration and passes them to `WithBindMount`.
- Committed files show only placeholders. `README.md` documents the `dotnet user-secrets set` commands with placeholder values.

**Alternative:** a `.env` file. The AppHost would need extra loading code for it, while user secrets already live outside the repo.

### 5. ComfyUI container and workflow files
- **Image:** a CUDA base, with ComfyUI and its custom nodes installed by `comfy-cli` at pinned versions. It runs headless (`--listen`), and its port is published to localhost.
- **Developer access:** during development the `comfy` CLI targets this instance. It is the single ComfyUI on the GPU, and `CLAUDE.md` forbids the GUI.
- **Workflow files:** each operation lives in `comfyui/workflows/<name>.json` in **API format**.
  - **Inputs** are nodes whose title starts with `in:`. For example, `in:prompt`, `in:seed`, `in:reference_1` and `in:use_reference_1` get the job's values in their primary widget.
  - **Outputs** are save nodes titled `out:<name>`.
  - The worker only substitutes values, submits the workflow, watches progress over the websocket, and uploads the outputs. No per-workflow code.
- **Alternative:** UI-format files with favourites, as in video-bot. They need UI-to-API conversion in the worker. A title convention keeps the files editable through the CLI and needs no converter.

### 6. First workflows
- **`style-anchor`:** FLUX.2 klein 4B (Apache 2.0) taking text plus up to 3 references. It reuses video-bot's slot-and-placeholder pattern.
- **`turnaround`:** same model. The pack's picked anchor image is reference 1. The prompt asks for a 3:1 sheet of front, side and top orthographic views of a single object on a flat background.
  - View regions are the three equal horizontal thirds of the image. The worker records them as fixed rectangles.
  - **Alternative:** three separate generations, one per view. They drift apart in detail and proportion.
- **`segment-parts`:** text-prompted detection plus masks, from a maintained ComfyUI node pack for GroundingDINO+SAM 2 or SAM 3, picked with the CLI during implementation.
  - It runs per view region.
  - The worker computes each mask's bounding box and area with `numpy`/`pillow` and stores masks as PNG files.
  - Parts that are not found are listed as missing.

### 7. Geometry: mesh-native part library on `bpy`, not a CAD kernel
**Why not CAD:** tessellating BREP solids gives triangle fans and slivers, which ruin low-poly topology, bevels and UVs later.

`slopoly_model` is a thin Python API over `bmesh`, run inside the `bpy` wheel from PyPI. The container's Python matches the version that wheel requires.

```python
part("bed", box(1.2, 0.3, 0.7), at=(0, 0.5, 0))
part("handle_L", sweep(path=[...], profile=ngon(6, r=0.03)), parent="bed", mirror="x")
part("axle", prism(6, r=0.04, length=1.0, axis="x"), parent="bed",
     joint=rotate(axis="x"))                    # origin on the axis -> pivot
part("wheel_L", prism(8, r=0.3, length=0.08, axis="x"), parent="axle", mirror="x")
instance("plank", count=30, transforms=[...])   # shared mesh, many nodes
```

- **Operations:** primitives (`box`, `prism(n)`, `cone(n)`, `ngon`), `extrude`, `inset`, `bevel` (bmesh ops) and `boolean`, kept minimal.
- **Booleans** run through `manifold3d` and are reported in the build, because they degrade topology.
- **Mirror** copies and negates. The result is exact, and the spec checks that.
- **Instances** become linked duplicates, which the glTF exporter writes as one mesh with many nodes.
- **Joints** set the node's origin and axis, and add named empties (`socket_*`) for connection points.

**Build job flow:**
1. Run the program in a subprocess with a timeout.
2. Collect the parts.
3. Run validators with `manifold3d`:
   - pairwise intersection volume;
   - contact, checked as distance ≤ tolerance via `trimesh` proximity;
   - a connectivity graph from root;
   - polygon count.
4. Score silhouettes.
5. Export GLB with Blender's glTF exporter (Y up, metres).
6. Upload the GLB plus a JSON report.

Errors are returned with the program's line number from the traceback.

### 8. Silhouette scoring without rendering
- For each view, the parts are projected orthographically onto the view plane, and their triangles are filled with `pillow` at the mask's resolution.
- **Alignment:** the projection of the whole object is scaled and translated so its bounding box matches the union of that view's masks. Absolute size therefore comes from the program, not the image. Per-part scores then give:
  - IoU;
  - signed width and height error as a fraction of the object's size;
  - centre offset.
- **Alternative:** Blender rendering. Rendering needs OpenGL/EGL or Cycles CPU in the container and would be slower, while a silhouette is only filled polygons.

### 9. Agent: Claude Agent SDK as a worker
- **Turns as jobs:** the agent container is a `slopoly_worker` that consumes `jobs.agent-turn`. Each user chat message creates one.
- **Running a turn:** the handler runs the Python Claude Agent SDK, which drives the Claude Code CLI.
  - Credentials come from `CLAUDE_CODE_OAUTH_TOKEN`, populated from the `claude-oauth-token` parameter.
  - The session is resumed from the pack's stored session id.
  - The SDK's streamed messages are forwarded as job events, so the chat panel renders them live.
- **Benefits:** no inbound port, and cancellation, retry and redelivery come from the queue. The same outbound-only property holds for a future cloud API, where workers would connect over AMQPS.
- **Sessions:** Claude Code session files live in a named Docker volume, so `--resume` survives container restarts.
- **Authorisation:** README step: run `claude setup-token` (in the agent container through the Aspire dashboard terminal, or on the host) and paste the token into the parameter. A 401 from the SDK fails the turn with a distinct `auth` error, and the chat shows re-authorisation steps.
- **Agent configuration:** the agent's working directory is `agent/` from the repo, mounted read-only. It holds the agent's `CLAUDE.md` (pipeline, rules and the `slopoly_model` API reference). The SDK is configured with only the Slopoly MCP server and no shell or file-write tools.
- **Alternative:** a Node bridge with the TypeScript SDK and its own HTTP/WebSocket API. That means a second language for workers and a second streaming protocol.

### 10. MCP server in the API
- Uses the official C# MCP SDK (`ModelContextProtocol.AspNetCore`) over streamable HTTP, protected by `worker-key`.
- Tools are thin wrappers over the same application services the REST endpoints use: `get_pack`, `update_style`, `create_asset`, `start_job`, `get_job`, `cancel_job`, `retry_job`, `list_concepts`, `get_segmentation`, `get_part_colors`, `get_palette`, `upsert_palette_entries`, `upsert_palette_variant`, `save_manifest`, `submit_program`, `get_build_report`, `view_image`.
- Results are JSON with ids and numbers. `view_image` is the only tool that returns image content.

### 11. Web UI
- MudBlazor components only, with no custom CSS beyond layout tweaks. Data comes from typed `HttpClient`s against the API, and live refresh comes from the SignalR client.
- Pages: Packs, Pack (style guide, concept gallery with pick/reject, assets, jobs, chat drawer), and Asset (manifest, program versions, builds, validator and score tables, 3D viewer).
- The 3D viewer is Google's `<model-viewer>` web component, a vendored pinned file in `wwwroot` with a tiny Razor wrapper.

### 12. Data model (EF Core, SQLite, migrations)
`Pack`, `StyleReference`, `Asset`, `ConceptImage` (with selection and source job), `PartColors` (measured per mask), `PaletteEntry` (role, kind, slot index, main colours), `PaletteVariant` and `PaletteVariantColor` (variant × role → colours), `Manifest`, `ProgramVersion`, `Build` (with report JSON, GLB file and the roles it uses), `Job`, `JobEvent`, `ChatSession`, and `StoredFile` (path under `<data-dir>/files`, content type, hash).

### 13. Palette: data in SQLite, texture as a derived file
- **The palette is rows, not a document.** Each entry has a role name, kind (solid or gradient), one or two colours and a slot index assigned once at creation. Variants store only colours per role. Missing variant colours fall back to the main colour, so a new role appears in every variant automatically.
- **Fixed layout derived from slot indices.** One 256×256 texture: the top half is a grid of 8×8 px solid cells (up to 256 entries) and the bottom half holds 4 px high horizontal gradient strips (up to 32). A slot maps to the same rectangle forever, so UVs never change when colours change. Colours are sampled at cell centres with nearest filtering, and each gradient's UVs stay inside its strip with a half-pixel inset to avoid bleeding.
- **One Python module owns the layout.** `slopoly_model.palette` both renders the texture (Pillow) and computes UVs, so the two cannot drift apart.
- **Recolouring is a quick `palette-render` job on the geometry worker.** It renders the main and variant textures. For each current build of the pack it replaces the GLB's embedded image with the new main texture; geometry, UVs and the program are untouched. The API marks palette textures stale on any colour edit and debounces the job (about 1 s) so dragging a colour picker doesn't queue dozens of jobs.
  - *Alternative:* render the PNG in the API with an image library. That duplicates the layout logic in C# and adds a .NET imaging dependency (ImageSharp has a split commercial licence).
- **UV assignment at build time.**
  - *Solid role:* all of a face's UVs go to the cell centre.
  - *Gradient role:* each vertex's position along the tagged axis, normalised over that part's or face group's extent, maps to the strip from start to end.
  - Material tags apply to a whole part or to a named face group created by the `slopoly_model` ops (for example `extrude(..., tag="top")`). Faces with no tag inherit their part's tag; a part with no tag fails the build.
- **Colour measurement** is part of the `segment-parts` job: per mask, k-means over its pixels in Lab colour space (k ≤ 4), dropping clusters under 5 % coverage. It returns hex and coverage, and is stored as `PartColors`.
- **Colour likeness** in the build report: per part and view, the CIEDE2000 difference between the tagged role's main colour (the gradient's mean for gradients) and the mask's dominant colour.
- **Generation uses the main palette only.** Builds, scores and the agent's tools read main-palette colours. Variants are touched only by variant tools, the palette-render job and the viewer.
- **Preview and export.** The viewer loads the GLB and, when a variant is chosen, swaps the material's base-colour texture through `<model-viewer>`'s scene-graph API, so no rebuild or job is needed. Exports embed the main texture and add `palette_<variant>.png` files next to the GLB.
- **UI:** a palette editor on the Pack page with MudBlazor colour pickers, a role-naming hint (usage by default, colour names only for colours fixed across palettes), a variant selector, and "used by" lists that block deletion of entries in use.

## Risks / Trade-offs

- **Turnaround sheets may not keep a three-panel layout or a shared scale** → fixed 3:1 size plus prompt wording. Scoring normalises per view, so moderate scale drift doesn't break it. If drift is common, the next change adds per-view generation with the sheet as reference.
- **Text-prompted segmentation can miss small parts** (an axle hidden behind wheels) → missing parts are reported rather than fatal. The agent sizes them from the manifest and its neighbours.
- **Subscription tokens can expire or be rejected in containers** (community reports disagree on lifetime) → a distinct auth error and re-auth guidance in the UI. Using a personal subscription is acceptable only for this single-user local app, and a hosted version would need different auth.
- **Agent convergence is unproven** → validators and scores are numeric, so the agent can iterate cheaply. The cart scenario is the acceptance test, and the agent reports blockers instead of looping. Turns have a maximum-turns setting.
- **Container I/O on a Windows bind mount is slower** → it only affects model load time. Models stay loaded between jobs.
- **`bpy` wheels pin a specific Python version and are large** → the geometry image is built once, and the version is pinned.
- **A writable models mount lets the container write to the shared folder** → this is intended, so downloads are shared. Documented in README.
- **Redelivery can run a job twice** (a worker dies after uploading but before acknowledging) → handlers are idempotent per job id: outputs are keyed by job and attempt, and the API accepts only the first `succeeded` per job.
- **The broker and SQLite can disagree** (publish fails after the row is saved) → the API publishes right after saving and marks the job failed with a "dispatch failed" error if publishing throws; the user or agent retries. No outbox, which is acceptable for a local single-user app.
- **Mask colours include shading and outlines** (stylised images have dark edges and lighting) → dominant cluster per mask, small clusters dropped. The measured colours are only starting points; the agent and user name and adjust them.
- **Palette capacity** (256 solids, 32 gradients per pack) → ample for a low-poly pack. The layout is versioned, so a larger texture can be added later without moving existing slots.
- **Python tests run in containers, so they are slower than host runs** → the containers mount the source read-only so a test run needs no image rebuild.

## Migration Plan

Greenfield; the sample weather code is removed. Rollback is a git revert. There's no persistent data before this change.

## Open Questions

- Which segmentation node pack: GroundingDINO+SAM 2 or SAM 3. Pick whichever runs headless in the container within 12 GB alongside nothing else; the job contract stays the same.
- Default polygon budget per pack (proposed: 2,000 triangles for props). It can be tuned later in the pack settings.
