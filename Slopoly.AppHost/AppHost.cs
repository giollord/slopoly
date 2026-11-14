var builder = DistributedApplication.CreateBuilder(args);

var repoRoot = Path.GetFullPath(Path.Combine(builder.AppHostDirectory, ".."));

// Machine-specific values come from user secrets (Parameters:<name>), never from tracked files. See README.md.
var dataDir = builder.AddParameter("data-dir", Path.Combine(repoRoot, ".data"))
    .WithDescription("Folder for the SQLite database and generated files.");
var workerKey = builder.AddParameter("worker-key",
    new GenerateParameterDefault { MinLength = 32, Special = false }, secret: true, persist: true);
var modelsDir = builder.AddParameter("comfyui-models-dir")
    .WithDescription("Host folder with ComfyUI models (checkpoints, diffusion_models, ...). Mounted writable into the ComfyUI container.");
var claudeToken = builder.AddParameter("claude-oauth-token", secret: true)
    .WithDescription("Token from `claude setup-token` (Claude subscription).");

var rabbitmq = builder.AddRabbitMQ("rabbitmq")
    .WithManagementPlugin()
    .WithDataVolume()
    .WithBindMount(Path.Combine(repoRoot, "containers", "rabbitmq", "20-slopoly.conf"),
        "/etc/rabbitmq/conf.d/20-slopoly.conf", isReadOnly: true);

var apiService = builder.AddProject<Projects.Slopoly_ApiService>("apiservice")
    .WithHttpHealthCheck("/health")
    .WithReference(rabbitmq)
    .WaitFor(rabbitmq)
    .WithEnvironment("Slopoly__DataDir", dataDir)
    // Global technique notes live in the repo, so notes the agent writes show up in git (design section 6).
    .WithEnvironment("Slopoly__KnowledgeDir", Path.Combine(repoRoot, "knowledge"))
    .WithEnvironment("Slopoly__WorkerKey", workerKey);

// Workers reach the broker and the API over connections they open themselves (design section 1).
IResourceBuilder<ContainerResource> Worker(IResourceBuilder<ContainerResource> container) => container
    .WithReference(rabbitmq).WaitFor(rabbitmq)
    .WithEnvironment("SLOPOLY_API_URL", apiService.GetEndpoint("http"))
    .WithEnvironment("SLOPOLY_WORKER_KEY", workerKey)
    .WaitFor(apiService);

// ComfyUI needs the models folder at container creation; without it the resource stays unstarted until configured.
var comfyui = Worker(builder.AddDockerfile("comfyui", repoRoot, "containers/comfyui/Dockerfile"))
    .WithContainerRuntimeArgs("--gpus", "all")
    .WithBindMount(Path.Combine(repoRoot, "comfyui", "workflows"), "/opt/slopoly/workflows", isReadOnly: true)
    .WithEnvironment("COMFYUI_ARGS", builder.Configuration["ComfyUiArgs"] ?? "--reserve-vram 3")
    .WithHttpEndpoint(port: 8288, targetPort: 8188, name: "comfyui")
    .WithVolume("slopoly-comfyui-user", "/opt/ComfyUI/user");
if (builder.Configuration["Parameters:comfyui-models-dir"] is { Length: > 0 } models)
    comfyui.WithBindMount(models, "/opt/ComfyUI/models");
else
    comfyui.WithExplicitStart().WaitFor(modelsDir);

// Geometry worker: part programs -> validated GLB (CPU, Blender as a Python module).
Worker(builder.AddDockerfile("geometry", repoRoot, "containers/geometry/Dockerfile"));

// Design agent: Claude Code on the user's subscription; app access only through the API's MCP tools.
var agent = Worker(builder.AddDockerfile("agent", repoRoot, "containers/agent/Dockerfile"))
    .WithBindMount(Path.Combine(repoRoot, "agent"), "/opt/slopoly/agent", isReadOnly: true)
    .WithVolume("slopoly-agent-claude", "/home/agent/.claude");
// Without a token the agent still runs and answers each chat turn with an "auth" error that explains the setup.
if (builder.Configuration["Parameters:claude-oauth-token"] is { Length: > 0 })
    agent.WithEnvironment("CLAUDE_CODE_OAUTH_TOKEN", claudeToken);

builder.AddProject<Projects.Slopoly_Web>("webfrontend")
    .WithExternalHttpEndpoints()
    .WithHttpHealthCheck("/health")
    .WithReference(apiService)
    .WaitFor(apiService);

// Python tests run in containers too (no host Python); start this resource from the dashboard to run them.
foreach (var tests in new[] { "tests", "geometry-tests", "agent-tests" })
    builder.AddExecutable($"python-{tests}", "docker", repoRoot, "compose", "-f", "workers/compose.test.yaml", "run", "--rm", "--build", tests)
        .WithExplicitStart();

builder.Build().Run();
