# Slopoly

A local browser app that turns a short brief into low-poly 3D game assets: style-consistent concept images
(ComfyUI), part programs written by a Claude agent, validated multi-part geometry (Blender) coloured through a shared
palette texture, exported as GLB.

## Requirements

- Docker Desktop (WSL 2 backend) with the [NVIDIA Container Toolkit](https://docs.nvidia.com/datacenter/cloud-native/container-toolkit/install-guide.html)
- An NVIDIA GPU (designed for 12 GB VRAM)
- .NET SDK 11 and the [Aspire CLI](https://aspire.dev)
- A Claude subscription (Pro or Max) for the agent

Nothing else is installed on the host: Python, ComfyUI, Blender, RabbitMQ and the agent run in containers.

## Configuration

Machine-specific values are AppHost parameters. Set them once in user secrets (stored outside the repository), or
enter them when the Aspire dashboard asks for them:

```sh
cd Slopoly.AppHost
dotnet user-secrets set "Parameters:comfyui-models-dir" "<models-dir>"     # host folder with ComfyUI models
dotnet user-secrets set "Parameters:claude-oauth-token" "<token>"          # see "Authorising the agent"
dotnet user-secrets set "Parameters:data-dir" "<data-dir>"                 # optional; default: .data in the repo
```

- `comfyui-models-dir` is mounted **writable** into the ComfyUI container, so models downloaded there land in your
  folder and can be shared with other ComfyUI installs. The required models are listed in `comfyui/README.md`.
- `worker-key` (the workers' and agent's API key) and the RabbitMQ credentials are generated automatically.

After changing `comfyui-models-dir`, restart the AppHost: the folder is mounted when the container is created.

## Run

```sh
aspire start
```

Open the `webfrontend` URL from the dashboard.

## Authorising the agent

The agent runs Claude Code on your subscription, not on API keys.

1. Run `claude setup-token` and complete the sign-in in your browser. It can run in the agent container
   (`docker exec -it <agent container> claude setup-token`; find the container with `docker ps`) or on any machine
   with Claude Code.
2. Store the printed token: `dotnet user-secrets set "Parameters:claude-oauth-token" "<token>" --project Slopoly.AppHost`,
   then restart the AppHost (`aspire stop`, `aspire start`).
3. Until a token is set, and whenever it expires or is revoked, each chat message fails with an authorisation error
   that repeats these steps.

The subscription is for your own use of this local app; a hosted, multi-user deployment would need API-key auth.

## Tests

```sh
dotnet test Slopoly.Tests                                       # .NET (starts containers through Aspire testing)
docker compose -f workers/compose.test.yaml run --rm tests            # Python workers, in a container
docker compose -f workers/compose.test.yaml run --rm geometry-tests   # geometry (bpy)
docker compose -f workers/compose.test.yaml run --rm agent-tests      # agent worker (stubbed SDK)
```
