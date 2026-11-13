# Proposal

## Why

Slopoly should turn a short brief ("low-poly gnome village, quirky, vibrant") into game-ready 3D assets with clean, symmetric, low-poly topology, not the lumpy remeshed output of voxel-based 3D generators. Today the repo is only the Aspire starter. Before any one feature is worth polishing, we need a thin path that runs end to end: a brief, style-consistent concept images, a part program written by an agent, validated geometry and an exported model. Building that path is also the cheapest way to find out whether an agent can make a part program converge on a concept image.

## What Changes

- Replace the starter sample code (weather pages and endpoint) with the Slopoly foundation. The app runs locally in the browser with one `aspire start`.
- **Packs and assets.** A pack carries general instructions and a style guide (text plus reference images). It owns assets, each with concept images (picked or rejected), a part manifest, a versioned part program and builds. Data lives in SQLite and files on disk.
- **Job queue.** Background work runs as jobs. Workers connect outbound to the API, claim jobs, report progress, and can be cancelled or retried. GPU work runs one job at a time.
- **ComfyUI container.** ComfyUI runs headless with GPU access. Its models folder is bind-mounted from a host folder that is configured locally and never committed. Workflows are files in the repo, built with the `comfy` CLI. The first workflows are:
  - a style anchor (scene) image;
  - a style-referenced orthographic turnaround of one object;
  - text-prompted part segmentation.
- **Geometry worker container.** Blender (`bpy`) with a small mesh-native part-modelling library. It covers:
  - primitives with explicit segment counts, extrude, inset and bevel;
  - mirror symmetry, instances, joints and pivots;
  - validators: intersection volume, contact, floating parts and polygon budget;
  - silhouette scoring against segmentation masks;
  - canonical GLB export.
- **Design agent container.** Runs Claude Code headless on the user's Claude subscription, authorised through the user's browser. It works on the app only through an MCP server hosted by the API. It avoids viewing images and relies on tools that return numbers and IDs.
- **Web UI (MudBlazor):**
  - packs and style guides;
  - a concept gallery for picking and rejecting images;
  - a job list;
  - a per-pack chat with the agent;
  - an asset page with builds, validator reports and an in-browser 3D viewer.
- **First end-to-end target:** a low-poly wooden cart, from brief to validated, mirrored, multi-part GLB with a spinning wheel/axle pivot.
- **Repo conventions** for agents (`CLAUDE.md`):
  - ComfyUI workflows are built only through the `comfy` CLI against the container's ComfyUI, never its GUI;
  - write minimal code and prefer popular, maintained libraries;
  - never commit machine-specific paths or secrets.

## Capabilities

### New Capabilities

- `local-runtime`: one-command local start of all services, machine-specific configuration (models folder, data folder, agent token) kept out of the repository, and service health.
- `asset-packs`: packs, their instructions and style guides, assets, concept images and their selection, manifests, part-program versions and builds, stored as SQLite data and files.
- `generation-jobs`: the job queue: submit, claim by outbound workers, progress, cancel, retry, lease expiry, and serialized GPU work.
- `image-generation`: ComfyUI-backed generation of style-anchor images, style-referenced orthographic object turnarounds and part segmentation masks, driven by versioned workflow files.
- `part-modeling`: compiling a part program into low-poly meshes with symmetry, instances, joints and pivots; validating fit; scoring silhouettes against masks; exporting GLB.
- `design-agent`: the Claude Code agent: subscription authorisation, per-pack chat sessions, the MCP tool surface it uses to drive the pipeline, and its token-saving behaviour.

### Modified Capabilities

(none; there are no existing specs)

## Impact

- **Code:**
  - `Slopoly.AppHost` gains container resources, parameters and a bind mount.
  - `Slopoly.ApiService` gains EF Core SQLite, the job API, file storage, SignalR events and the MCP server.
  - `Slopoly.Web` gains MudBlazor pages and the chat panel.
  - The sample weather code is removed.
- **New folders:** `containers/comfyui`, `containers/geometry`, `containers/agent`, `workers/` (shared Python worker client), `comfyui/workflows/`, `agent/` (agent instructions).
- **Dependencies:** MudBlazor, EF Core SQLite, the official MCP C# SDK, the SignalR client, `<model-viewer>` for 3D preview, and the Claude Agent SDK for TypeScript. In Python: `bpy`, `manifold3d`, `trimesh`, `numpy`, `pillow`, `httpx`. ComfyUI is installed with `comfy-cli`.
- **Host requirements:**
  - Docker Desktop with WSL 2 and the NVIDIA Container Toolkit;
  - an NVIDIA GPU with 12 GB VRAM (the design target);
  - a host models folder;
  - a Claude subscription.
- **Out of scope:**
  - MAUI or desktop shell;
  - palette texturing and texture projection;
  - modular kits;
  - Godot/Unity export profiles;
  - image-to-3D proxy models;
  - cloud deployment and tunnelling (the outbound-worker design keeps it possible).
