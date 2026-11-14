using System.Text.Json.Serialization;
using Microsoft.EntityFrameworkCore;
using ModelContextProtocol.Protocol;
using Slopoly.ApiService.Data;
using Slopoly.ApiService.Endpoints;
using Slopoly.ApiService.Infrastructure;
using Slopoly.ApiService.Jobs;
using Slopoly.ApiService.Mcp;
using Slopoly.ApiService.Studio;
using Slopoly.Contracts;

var builder = WebApplication.CreateBuilder(args);

builder.AddServiceDefaults();

var options = builder.Configuration.GetSection("Slopoly").Get<SlopolyOptions>() ?? new SlopolyOptions();
options.DataDir = Path.GetFullPath(options.DataDir);
Directory.CreateDirectory(options.DataDir);
builder.Services.AddSingleton(options);

builder.Services.AddDbContext<SlopolyDb>(db => db.UseSqlite($"Data Source={Path.Combine(options.DataDir, "slopoly.db")}"));
builder.AddRabbitMQClient("rabbitmq");

builder.Services.AddProblemDetails();
builder.Services.AddOpenApi();
builder.Services.AddSignalR().AddJsonProtocol(o => o.PayloadSerializerOptions.Converters.Add(new JsonStringEnumConverter()));
builder.Services.ConfigureHttpJsonOptions(o => o.SerializerOptions.Converters.Add(new JsonStringEnumConverter()));
Broker.Json.Converters.Add(new JsonStringEnumConverter());

builder.Services.AddSingleton<Broker>();
builder.Services.AddSingleton<Notifier>();
builder.Services.AddSingleton<PaletteRenderScheduler>();
builder.Services.AddScoped<FileStore>();
builder.Services.AddScoped<JobService>();
builder.Services.AddScoped<StudioService>();
builder.Services.AddScoped<GenerationService>();
builder.Services.AddScoped<PaletteService>();
builder.Services.AddScoped<JobEventApplier>();
builder.Services.AddScoped<IJobResultHandler, ConceptImageResults>();
builder.Services.AddScoped<IJobResultHandler, ViewsResults>();
builder.Services.AddScoped<IJobResultHandler, SegmentationResults>();
builder.Services.AddScoped<IJobResultHandler, BuildResults>();
builder.Services.AddScoped<IJobResultHandler, AgentTurnResults>();
builder.Services.AddScoped<IJobResultHandler, SceneResults>();
builder.Services.AddScoped<KnowledgeService>();
builder.Services.AddScoped<IJobResultHandler, PaletteRenderResults>();
builder.Services.AddHostedService<JobEventConsumer>();
builder.Services.AddMcpServer()
    .WithHttpTransport(o => o.Stateless = true)
    .WithTools<StudioTools>(new System.Text.Json.JsonSerializerOptions(Broker.Json) { TypeInfoResolver = new System.Text.Json.Serialization.Metadata.DefaultJsonTypeInfoResolver() })
    .WithRequestFilters(f => f.AddCallToolFilter(next => async (request, ct) =>
    {
        try { return await next(request, ct); }
        catch (StudioException ex) { return new() { IsError = true, Content = [new TextContentBlock { Text = ex.Message }] }; }
    }));

var app = builder.Build();

await using (var scope = app.Services.CreateAsyncScope())
    await scope.ServiceProvider.GetRequiredService<SlopolyDb>().Database.MigrateAsync();
await using (var channel = await app.Services.GetRequiredService<RabbitMQ.Client.IConnection>().CreateChannelAsync())
    await Broker.DeclareTopologyAsync(channel);

app.UseExceptionHandler();
app.UseStudioErrors();
app.UseWorkerKey();
if (app.Environment.IsDevelopment()) app.MapOpenApi();

app.MapGet("/", () => "Slopoly API");
app.MapStudioApi();
app.MapHub<EventsHub>(Realtime.Path);
app.MapMcp("/mcp");
app.MapDefaultEndpoints();

app.Run();

