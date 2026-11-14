# Slopoly: notes for Claude

Slopoly is a local browser app that generates low-poly 3D game assets in packs. It is orchestrated by Aspire:
the API (`Slopoly.ApiService`), the Blazor UI (`Slopoly.Web`), RabbitMQ, and three worker containers
(`containers/comfyui`, `containers/geometry`, `containers/agent`). Planning lives in `openspec/`.

## Rules

- **Minimal code.** Prefer abstraction and reuse over new code. If a popular, maintained library does the job, use
  it (MudBlazor for UI, EF Core, Aspire integrations, RabbitMQ.Client, aio-pika, manifold3d, trimesh, ...). No
  obscure or unmaintained packages.
- **The repo is public.** Never commit host paths, user names or tokens, including in specs and docs. Use
  placeholders such as `<models-dir>` and `<data-dir>`; real values live in AppHost user secrets.
- **Host dependencies.** The app needs only Docker Desktop (with the NVIDIA Container Toolkit), the .NET SDK and the
  Aspire CLI. All Python runs in containers, including Python tests (`aspire` resource command or
  `docker compose -f workers/compose.test.yaml run --rm tests`). The developer's host Python and `comfy` CLI may be
  used while developing, never as an app dependency.
- **ComfyUI workflows** are built only with the `comfy` CLI against the container's ComfyUI (published on localhost;
  see `comfyui/README.md`), never through the ComfyUI GUI. Start from templates. Workflow files are API format;
  inputs are nodes titled `in:<name>`, outputs are save nodes titled `out:<name>`.
- Only one ComfyUI may use the GPU at a time: don't run jobs on a host ComfyUI while the container's is busy.

## Commands

```sh
aspire start --non-interactive        # whole stack
aspire describe --non-interactive     # resource states
aspire stop --non-interactive
dotnet test Slopoly.Tests             # .NET tests (start containers through Aspire testing)
docker compose -f workers/compose.test.yaml run --rm tests            # Python tests, in a container
docker compose -f workers/compose.test.yaml run --rm geometry-tests   # geometry (bpy) tests
docker compose -f workers/compose.test.yaml run --rm agent-tests      # agent worker tests (stubbed SDK)
```
