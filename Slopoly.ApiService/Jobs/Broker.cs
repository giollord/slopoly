using System.Text.Json;
using System.Text.Json.Nodes;
using RabbitMQ.Client;

namespace Slopoly.ApiService.Jobs;

/// <summary>
/// RabbitMQ topology (design §2) and publishing. The Python workers declare the same names; keep
/// <c>workers/slopoly_worker/protocol.py</c> in sync.
/// </summary>
public sealed class Broker(IConnection connection) : IAsyncDisposable
{
    public const string JobsExchange = "jobs";              // direct, routing key = kind
    public const string EventsExchange = "job-events";      // topic, routing key = <kind>.<type>
    public const string ControlExchange = "job-control";    // fanout
    public const string ApiEventsQueue = "api.job-events";
    public static string JobQueue(string kind) => $"jobs.{kind}";

    public static readonly JsonSerializerOptions Json = new(JsonSerializerDefaults.Web);

    private readonly SemaphoreSlim _lock = new(1, 1);
    private IChannel? _channel;

    /// <summary>Declares exchanges and queues; idempotent.</summary>
    public static async Task DeclareTopologyAsync(IChannel channel, CancellationToken ct = default)
    {
        await channel.ExchangeDeclareAsync(JobsExchange, ExchangeType.Direct, durable: true, cancellationToken: ct);
        await channel.ExchangeDeclareAsync(EventsExchange, ExchangeType.Topic, durable: true, cancellationToken: ct);
        await channel.ExchangeDeclareAsync(ControlExchange, ExchangeType.Fanout, durable: true, cancellationToken: ct);
        foreach (var kind in Contracts.JobKinds.All)
        {
            await channel.QueueDeclareAsync(JobQueue(kind), durable: true, exclusive: false, autoDelete: false, cancellationToken: ct);
            await channel.QueueBindAsync(JobQueue(kind), JobsExchange, kind, cancellationToken: ct);
        }
        await channel.QueueDeclareAsync(ApiEventsQueue, durable: true, exclusive: false, autoDelete: false, cancellationToken: ct);
        await channel.QueueBindAsync(ApiEventsQueue, EventsExchange, "#", cancellationToken: ct);
    }

    public Task PublishJobAsync(JobMessage message, CancellationToken ct = default) =>
        PublishAsync(JobsExchange, message.Kind, message, ct);

    public Task PublishCancelAsync(Guid jobId, CancellationToken ct = default) =>
        PublishAsync(ControlExchange, "", new ControlMessage("cancel", jobId), ct);

    /// <summary>Publishes a persistent JSON message and waits for the broker's confirmation (throws when refused).</summary>
    public async Task PublishAsync<T>(string exchange, string routingKey, T message, CancellationToken ct = default)
    {
        var body = JsonSerializer.SerializeToUtf8Bytes(message, Json);
        var properties = new BasicProperties { Persistent = true, ContentType = "application/json" };
        await _lock.WaitAsync(ct);
        try
        {
            _channel ??= await connection.CreateChannelAsync(new CreateChannelOptions(
                publisherConfirmationsEnabled: true, publisherConfirmationTrackingEnabled: true), ct);
            await _channel.BasicPublishAsync(exchange, routingKey, mandatory: true, properties, body, ct);
        }
        catch
        {
            // A failed channel can't be reused; open a fresh one next time.
            if (_channel is { IsOpen: false }) _channel = null;
            throw;
        }
        finally { _lock.Release(); }
    }

    public async ValueTask DisposeAsync()
    {
        if (_channel is not null) await _channel.DisposeAsync();
    }
}

public sealed record JobMessage(Guid JobId, string Kind, string? Operation, Guid? PackId, Guid? AssetId, JsonObject Inputs);

public sealed record ControlMessage(string Type, Guid JobId);

/// <summary>What a worker reports. <c>Type</c>: started, progress, stream, succeeded, failed.</summary>
public sealed record WorkerEvent(Guid JobId, string Type, double? Progress, JsonObject? Data, JsonObject? Outputs,
    string? Error, string? ErrorCode);
