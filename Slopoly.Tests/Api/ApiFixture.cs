using System.Net.Http.Json;
using System.Text.Json;
using System.Text.Json.Nodes;
using System.Text.Json.Serialization;
using Microsoft.AspNetCore.Hosting;
using Microsoft.AspNetCore.Mvc.Testing;
using Microsoft.AspNetCore.SignalR.Client;
using RabbitMQ.Client;
using Slopoly.ApiService.Infrastructure;
using Slopoly.ApiService.Jobs;
using Slopoly.ApiService.Studio;
using Slopoly.Contracts;
using Testcontainers.RabbitMq;

namespace Slopoly.Tests.Api;

/// <summary>
/// One API instance (temp data dir) and one RabbitMQ container for all API tests. Tests create their own packs, and
/// play the worker role by consuming job queues and publishing events.
/// </summary>
[SetUpFixture]
public sealed class ApiFixture
{
    public const string WorkerKey = "test-worker-key";
    public static readonly JsonSerializerOptions Json = new(JsonSerializerDefaults.Web) { Converters = { new JsonStringEnumConverter() } };

    private static RabbitMqContainer _rabbit = null!;
    private static WebApplicationFactory<Broker> _factory = null!;
    private static string _dataDir = null!;
    public static IConnection Rabbit { get; private set; } = null!;
    public static IServiceProvider Services => _factory.Services;

    [OneTimeSetUp]
    public async Task StartAsync()
    {
        _rabbit = new RabbitMqBuilder("rabbitmq:4-management").Build();
        await _rabbit.StartAsync();
        _dataDir = Directory.CreateTempSubdirectory("slopoly-tests-").FullName;
        PaletteRenderScheduler.Delay = TimeSpan.FromMilliseconds(200);
        _factory = new WebApplicationFactory<Broker>().WithWebHostBuilder(b =>
        {
            b.UseSetting("ConnectionStrings:rabbitmq", _rabbit.GetConnectionString());
            b.UseSetting("Slopoly:DataDir", _dataDir);
            b.UseSetting("Slopoly:WorkerKey", WorkerKey);
        });
        _ = _factory.CreateClient();
        Rabbit = await new ConnectionFactory { Uri = new Uri(_rabbit.GetConnectionString()) }.CreateConnectionAsync();
    }

    [OneTimeTearDown]
    public async Task StopAsync()
    {
        await Rabbit.DisposeAsync();
        await _factory.DisposeAsync();
        await _rabbit.DisposeAsync();
        try { Directory.Delete(_dataDir, true); } catch (IOException) { }
    }

    public static HttpClient Client() => _factory.CreateClient();

    public static HttpClient WorkerClient()
    {
        var client = _factory.CreateClient();
        client.DefaultRequestHeaders.Add(Slopoly.ApiService.Infrastructure.WorkerKey.Header, WorkerKey);
        return client;
    }

    public static async Task<HubConnection> HubAsync()
    {
        var hub = new HubConnectionBuilder()
            .WithUrl(new Uri(_factory.Server.BaseAddress, Realtime.Path), o => o.HttpMessageHandlerFactory = _ => _factory.Server.CreateHandler())
            .AddJsonProtocol(o => o.PayloadSerializerOptions.Converters.Add(new JsonStringEnumConverter()))
            .Build();
        await hub.StartAsync();
        return hub;
    }

    public static async Task<T> ReadAsync<T>(HttpResponseMessage response)
    {
        if (!response.IsSuccessStatusCode)
            Assert.Fail($"{(int)response.StatusCode} {response.RequestMessage?.RequestUri}: {await response.Content.ReadAsStringAsync()}");
        return (await response.Content.ReadFromJsonAsync<T>(Json))!;
    }

    public static async Task<Pack> CreatePackAsync(string name = "Test pack") =>
        await ReadAsync<Pack>(await Client().PostAsJsonAsync("/api/packs", new PackEdit(name, "instructions", "quirky, vibrant", null), Json));

    /// <summary>Takes the next message of a job queue, like a worker would (auto-ack).</summary>
    public static async Task<JobMessage> TakeJobAsync(string kind, Guid jobId, TimeSpan? timeout = null)
    {
        // Hold other jobs' messages unacknowledged while searching (a requeued message returns to the head of the
        // queue), then give them back.
        await using var channel = await Rabbit.CreateChannelAsync();
        var deadline = DateTime.UtcNow + (timeout ?? TimeSpan.FromSeconds(10));
        var held = new List<ulong>();
        try
        {
            while (DateTime.UtcNow < deadline)
            {
                var result = await channel.BasicGetAsync(Broker.JobQueue(kind), autoAck: false);
                if (result is null) { await Task.Delay(50); continue; }
                var message = JsonSerializer.Deserialize<JobMessage>(result.Body.Span, Json)!;
                if (message.JobId == jobId) { await channel.BasicAckAsync(result.DeliveryTag, false); return message; }
                held.Add(result.DeliveryTag);
            }
        }
        finally
        {
            foreach (var tag in held) await channel.BasicNackAsync(tag, false, requeue: true);
        }
        throw new AssertionException($"No {kind} message for job {jobId}.");
    }

    public static async Task PublishEventAsync(string kind, Guid jobId, string type, JsonObject? outputs = null,
        double? progress = null, string? error = null, JsonObject? data = null)
    {
        await using var channel = await Rabbit.CreateChannelAsync();
        var body = JsonSerializer.SerializeToUtf8Bytes(new WorkerEvent(jobId, type, progress, data, outputs, error, null), Json);
        await channel.BasicPublishAsync(Broker.EventsExchange, $"{kind}.{type}", body);
    }

    public static async Task<Job> WaitForJobAsync(Guid jobId, Func<Job, bool> condition)
    {
        var client = Client();
        var deadline = DateTime.UtcNow + TimeSpan.FromSeconds(10);
        Job job;
        do
        {
            job = await ReadAsync<Job>(await client.GetAsync($"/api/jobs/{jobId}"));
            if (condition(job)) return job;
            await Task.Delay(50);
        } while (DateTime.UtcNow < deadline);
        Assert.Fail($"Job {jobId} stayed {job.State} (attempt {job.Attempt}).");
        return job;
    }

    /// <summary>Uploads a file as a worker and returns its id.</summary>
    public static async Task<Guid> UploadAsync(byte[] content, string name)
    {
        using var form = new MultipartFormDataContent { { new ByteArrayContent(content), "file", name } };
        return (await ReadAsync<StoredFile>(await WorkerClient().PostAsync("/worker/files", form))).Id;
    }
}
