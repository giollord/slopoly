using System.Security.Cryptography;
using Microsoft.AspNetCore.SignalR;
using Slopoly.ApiService.Data;
using Slopoly.Contracts;

namespace Slopoly.ApiService.Infrastructure;

public sealed class SlopolyOptions
{
    public string DataDir { get; set; } = ".data";
    /// <summary>Shared secret of the workers and the agent (header <see cref="WorkerKey.Header"/>).</summary>
    public string WorkerKey { get; set; } = "";
    /// <summary>Redeliveries after which a job fails instead of running again.</summary>
    public int MaxAttempts { get; set; } = 3;
    public string FilesDir => Path.Combine(DataDir, "files");
}

/// <summary>Files under &lt;data-dir&gt;/files, named by id, recorded as <see cref="StoredFile"/>.</summary>
public sealed class FileStore(SlopolyDb db, SlopolyOptions options)
{
    public string PathOf(Guid id) => Path.Combine(options.FilesDir, id.ToString("N"));

    /// <summary>Stores the stream and adds the record to the context (not saved).</summary>
    public async Task<StoredFile> AddAsync(Stream content, string name, string? contentType, CancellationToken ct = default)
    {
        Directory.CreateDirectory(options.FilesDir);
        var file = new StoredFile { Name = Path.GetFileName(name), ContentType = string.IsNullOrWhiteSpace(contentType) ? ContentTypes.For(name) : contentType };
        var path = PathOf(file.Id);
        await using (var target = File.Create(path))
        {
            using var hash = IncrementalHash.CreateHash(HashAlgorithmName.SHA256);
            var buffer = new byte[81920];
            int read;
            while ((read = await content.ReadAsync(buffer, ct)) > 0)
            {
                hash.AppendData(buffer, 0, read);
                await target.WriteAsync(buffer.AsMemory(0, read), ct);
            }
            file.Size = target.Length;
            file.Sha256 = Convert.ToHexStringLower(hash.GetHashAndReset());
        }
        db.Files.Add(file);
        return file;
    }

    public async Task<StoredFile> AddAsync(byte[] content, string name, string? contentType = null, CancellationToken ct = default)
    {
        using var stream = new MemoryStream(content);
        return await AddAsync(stream, name, contentType, ct);
    }
}

public static class ContentTypes
{
    private static readonly Microsoft.AspNetCore.StaticFiles.FileExtensionContentTypeProvider Provider = new()
    {
        Mappings = { [".glb"] = "model/gltf-binary", [".py"] = "text/x-python" },
    };

    public static string For(string name) =>
        Provider.TryGetContentType(name, out var type) ? type : "application/octet-stream";
}

public static class WorkerKey
{
    public const string Header = "X-Worker-Key";

    /// <summary>Paths only workers and the agent may call.</summary>
    public static readonly PathString[] Protected = ["/worker", "/mcp"];

    /// <summary>Answers 401 on protected paths unless the request carries the worker key.</summary>
    public static void UseWorkerKey(this WebApplication app) =>
        app.Use(async (context, next) =>
        {
            if (!Protected.Any(p => context.Request.Path.StartsWithSegments(p)) || IsWorker(context))
                await next(context);
            else
                context.Response.StatusCode = StatusCodes.Status401Unauthorized;
        });

    private static bool IsWorker(HttpContext context)
    {
        var expected = context.RequestServices.GetRequiredService<SlopolyOptions>().WorkerKey;
        var given = context.Request.Headers[Header].ToString();
        return expected.Length > 0 && CryptographicOperations.FixedTimeEquals(
            System.Text.Encoding.UTF8.GetBytes(given), System.Text.Encoding.UTF8.GetBytes(expected));
    }
}

public sealed class EventsHub : Hub;

/// <summary>Pushes change and job events to the UI.</summary>
public sealed class Notifier(IHubContext<EventsHub> hub)
{
    public Task Changed(string entity, Guid id, Guid? packId = null, Guid? assetId = null) =>
        hub.Clients.All.SendAsync(Contracts.Realtime.Changed, new ChangeEvent(entity, id, packId, assetId));

    public Task Changed<T>(Guid id, Guid? packId = null, Guid? assetId = null) => Changed(typeof(T).Name, id, packId, assetId);

    public Task JobEvent(Job job, string type, System.Text.Json.Nodes.JsonObject? data = null) =>
        hub.Clients.All.SendAsync(Contracts.Realtime.JobEvent,
            new JobEventMessage(job.Id, job.Kind, job.PackId, job.AssetId, job.State, type, data));
}
