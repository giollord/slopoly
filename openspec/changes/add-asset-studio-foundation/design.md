# Design

## Context

- The repo is the Aspire 13.6 starter on .NET 11: `Slopoly.AppHost`, `Slopoly.ApiService`, `Slopoly.Web` (Blazor Server), `Slopoly.ServiceDefaults`, and `Slopoly.Tests` (NUnit with Aspire testing). It contains only sample weather code.
- **Target machine:** Windows 11, Docker Desktop on WSL 2, an RTX 4070 with 12 GB VRAM, 64 GB RAM. Only one large model fits on the GPU at a time.
- **The repo will be public.** Host paths and tokens may appear only as placeholders such as `<models-dir>` and `<data-dir>`.
- **Code rule:** minimal code, reuse over bespoke infrastructure, and only popular, maintained packages.
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
             |  REST: packs, files, jobs (claim/lease/events)
             |  MCP (HTTP): agent tool surface
             |  SignalR hub: change + job events
             ^                ^                   ^
   outbound  |                |                   |
   +---------+---+    +-------+-------+    +------+-----------+
   | comfyui     |    | geometry      |    | agent            |
   | ComfyUI     |    | bpy +         |    | Claude Agent SDK |
   | + worker    |    | slopoly_model |    | (Claude Code)    |
   | GPU, models |    | + worker      |    | + worker         |
   +-------------+    +---------------+    +------------------+
```

**Alternative:** the API calling ComfyUI directly. It is simpler today, but it breaks the planned "API in the cloud, GPU at home" setup, and it needs a second integration style for geometry and the agent.

### 2. Job queue in SQLite with HTTP leases, not a message broker
- **Jobs table** holds kind, target, inputs JSON, state, lease expiry, attempt count and error.
- **Claiming:** workers call `POST /jobs/claim {kinds}`. A single conditional `UPDATE` claims the row, which is safe under SQLite's single-writer model.
- **While running:** the worker renews its lease via `POST /jobs/{id}/heartbeat`, which also returns `cancelRequested`. Progress and stream events are posted to `/jobs/{id}/events`.
- **Completion:** `POST /jobs/{id}/complete`. Outputs are uploaded as files first.
- **Background service:** a hosted service requeues jobs whose lease has expired.
- **Live updates:** every state change and event is broadcast on the SignalR hub.

**Alternative:** RabbitMQ through Aspire, as video-bot did. It is more robust, but it adds a broker container, plus leases and cancellation would still have to be built. A local single-user app with a handful of jobs per minute doesn't need it.

### 3. One shared Python worker client
`workers/slopoly_worker` is a small package used by all three containers. It handles:
- the claim, heartbeat, events and complete loop;
- file download and upload;
- cancellation, exposed as an `asyncio` cancel;
- a shared worker key header.

It uses `httpx` and `pydantic`. Each container adds only a handler per job kind.

**GPU serialization:** the ComfyUI container is the only GPU consumer in this change, and its worker runs one job at a time. ComfyUI starts with `--reserve-vram` (default 3 GB, configurable), because Windows holds GPU memory that the container cannot see.

### 4. Configuration through Aspire parameters
| Parameter | Kind | Default |
|---|---|---|
| `comfyui-models-dir` | plain | none, so the dashboard prompts and can save it to user secrets |
| `data-dir` | plain | `<repo>/.data` (git-ignored) |
| `claude-oauth-token` | secret | none, so the dashboard prompts |
| `worker-key` | secret | generated |

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
- **Turns as jobs:** the agent container is a `slopoly_worker` that claims `agent-turn` jobs. Each user chat message creates one.
- **Running a turn:** the handler runs the Python Claude Agent SDK, which drives the Claude Code CLI.
  - Credentials come from `CLAUDE_CODE_OAUTH_TOKEN`, populated from the `claude-oauth-token` parameter.
  - The session is resumed from the pack's stored session id.
  - The SDK's streamed messages are forwarded as job events, so the chat panel renders them live.
- **Benefits:** no inbound port, and cancellation, retry and lease recovery come from the queue. The same outbound-only property holds for a future cloud API.
- **Sessions:** Claude Code session files live in a named Docker volume, so `--resume` survives container restarts.
- **Authorisation:** README step: run `claude setup-token` (in the agent container through the Aspire dashboard terminal, or on the host) and paste the token into the parameter. A 401 from the SDK fails the turn with a distinct `auth` error, and the chat shows re-authorisation steps.
- **Agent configuration:** the agent's working directory is `agent/` from the repo, mounted read-only. It holds the agent's `CLAUDE.md` (pipeline, rules and the `slopoly_model` API reference). The SDK is configured with only the Slopoly MCP server and no shell or file-write tools.
- **Alternative:** a Node bridge with the TypeScript SDK and its own HTTP/WebSocket API. That means a second language for workers and a second streaming protocol.

### 10. MCP server in the API
- Uses the official C# MCP SDK (`ModelContextProtocol.AspNetCore`) over streamable HTTP, protected by `worker-key`.
- Tools are thin wrappers over the same application services the REST endpoints use: `get_pack`, `update_style`, `create_asset`, `start_job`, `get_job`, `cancel_job`, `retry_job`, `list_concepts`, `get_segmentation`, `save_manifest`, `submit_program`, `get_build_report`, `view_image`.
- Results are JSON with ids and numbers. `view_image` is the only tool that returns image content.

### 11. Web UI
- MudBlazor components only, with no custom CSS beyond layout tweaks. Data comes from typed `HttpClient`s against the API, and live refresh comes from the SignalR client.
- Pages: Packs, Pack (style guide, concept gallery with pick/reject, assets, jobs, chat drawer), and Asset (manifest, program versions, builds, validator and score tables, 3D viewer).
- The 3D viewer is Google's `<model-viewer>` web component, a vendored pinned file in `wwwroot` with a tiny Razor wrapper.

### 12. Data model (EF Core, SQLite, migrations)
`Pack`, `StyleReference`, `Asset`, `ConceptImage` (with selection and source job), `Manifest`, `ProgramVersion`, `Build` (with report JSON and GLB file), `Job`, `JobEvent`, `ChatSession`, and `StoredFile` (path under `<data-dir>/files`, content type, hash).

## Risks / Trade-offs

- **Turnaround sheets may not keep a three-panel layout or a shared scale** → fixed 3:1 size plus prompt wording. Scoring normalises per view, so moderate scale drift doesn't break it. If drift is common, the next change adds per-view generation with the sheet as reference.
- **Text-prompted segmentation can miss small parts** (an axle hidden behind wheels) → missing parts are reported rather than fatal. The agent sizes them from the manifest and its neighbours.
- **Subscription tokens can expire or be rejected in containers** (community reports disagree on lifetime) → a distinct auth error and re-auth guidance in the UI. Using a personal subscription is acceptable only for this single-user local app, and a hosted version would need different auth.
- **Agent convergence is unproven** → validators and scores are numeric, so the agent can iterate cheaply. The cart scenario is the acceptance test, and the agent reports blockers instead of looping. Turns have a maximum-turns setting.
- **Container I/O on a Windows bind mount is slower** → it only affects model load time. Models stay loaded between jobs.
- **`bpy` wheels pin a specific Python version and are large** → the geometry image is built once, and the version is pinned.
- **A writable models mount lets the container write to the shared folder** → this is intended, so downloads are shared. Documented in README.

## Migration Plan

Greenfield; the sample weather code is removed. Rollback is a git revert. There's no persistent data before this change.

## Open Questions

- Which segmentation node pack: GroundingDINO+SAM 2 or SAM 3. Pick whichever runs headless in the container within 12 GB alongside nothing else; the job contract stays the same.
- Default polygon budget per pack (proposed: 2,000 triangles for props). It can be tuned later in the pack settings.
