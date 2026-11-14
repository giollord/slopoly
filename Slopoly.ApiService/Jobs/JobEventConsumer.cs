using System.Text.Json;
using System.Text.Json.Nodes;
using RabbitMQ.Client;
using RabbitMQ.Client.Events;
using Slopoly.ApiService.Data;
using Slopoly.ApiService.Infrastructure;
using Slopoly.Contracts;

namespace Slopoly.ApiService.Jobs;

/// <summary>
/// Applies worker events to the job rows, stores them, applies results and broadcasts to the UI.
/// Rules: <c>started</c> counts an attempt; events for cancelled or finished jobs are ignored, so a late or duplicate
/// <c>succeeded</c> (redelivery) has no effect.
/// </summary>
public sealed class JobEventConsumer(IConnection connection, IServiceScopeFactory scopes, ILogger<JobEventConsumer> logger)
    : BackgroundService
{
    protected override async Task ExecuteAsync(CancellationToken stoppingToken)
    {
        var channel = await connection.CreateChannelAsync(cancellationToken: stoppingToken);
        await Broker.DeclareTopologyAsync(channel, stoppingToken);
        await channel.BasicQosAsync(0, 1, false, stoppingToken);
        var consumer = new AsyncEventingBasicConsumer(channel);
        consumer.ReceivedAsync += async (_, delivery) =>
        {
            try
            {
                var message = JsonSerializer.Deserialize<WorkerEvent>(delivery.Body.Span, Broker.Json);
                if (message is not null)
                {
                    await using var scope = scopes.CreateAsyncScope();
                    await scope.ServiceProvider.GetRequiredService<JobEventApplier>().ApplyAsync(message);
                }
            }
            catch (Exception ex)
            {
                // Poison or failing events must not block the queue; the job keeps its last good state.
                logger.LogError(ex, "Job event could not be applied");
            }
            await channel.BasicAckAsync(delivery.DeliveryTag, false, stoppingToken);
        };
        await channel.BasicConsumeAsync(Broker.ApiEventsQueue, autoAck: false, consumer, stoppingToken);
        try { await Task.Delay(Timeout.Infinite, stoppingToken); }
        catch (OperationCanceledException) { }
        await channel.DisposeAsync();
    }
}

public sealed class JobEventApplier(SlopolyDb db, Notifier notifier, IEnumerable<IJobResultHandler> handlers, ILogger<JobEventApplier> logger)
{
    public async Task ApplyAsync(WorkerEvent message)
    {
        var job = await db.Jobs.FindAsync(message.JobId);
        if (job is null) { logger.LogWarning("Event for unknown job {JobId}", message.JobId); return; }
        if (job.State is JobState.Cancelled or JobState.Succeeded or JobState.Failed) return;

        var now = DateTimeOffset.UtcNow;
        switch (message.Type)
        {
            case "started":
                job.State = JobState.Running;
                job.Attempt++;
                job.StartedAt = now;
                job.Progress = null;
                break;
            case "progress":
                job.Progress = message.Progress;
                break;
            case "stream":
                break;
            case "succeeded":
                job.Outputs = message.Outputs ?? [];
                try
                {
                    foreach (var handler in handlers.Where(h => h.Handles(job)))
                        await handler.ApplyAsync(job, job.Outputs);
                    job.State = JobState.Succeeded;
                    job.Progress = 1;
                }
                catch (Exception ex)
                {
                    logger.LogError(ex, "Result of job {JobId} could not be applied", job.Id);
                    job.State = JobState.Failed;
                    job.Error = $"The job's result could not be stored: {ex.Message}";
                    job.ErrorCode = "result_invalid";
                }
                job.FinishedAt = now;
                break;
            case "failed":
                job.State = JobState.Failed;
                job.Error = message.Error ?? "The job failed.";
                job.ErrorCode = message.ErrorCode;
                job.FinishedAt = now;
                break;
            default:
                logger.LogWarning("Unknown job event type {Type}", message.Type);
                return;
        }

        var data = message.Data;
        if (message.Type is "failed") data = new JsonObject { ["error"] = job.Error, ["code"] = job.ErrorCode };
        // Progress ticks are broadcast but not stored; everything else is history (chat streams included).
        if (message.Type != "progress")
            db.JobEvents.Add(new JobEvent { JobId = job.Id, Type = message.Type, Data = data?.DeepClone().AsObject(), At = now });
        await db.SaveChangesAsync();
        await notifier.JobEvent(job, message.Type, message.Type == "progress" ? new JsonObject { ["progress"] = job.Progress } : data);
    }
}

/// <summary>Turns a succeeded job's outputs into app records (concepts, masks, builds, ...). Saved by the caller.</summary>
public interface IJobResultHandler
{
    bool Handles(Job job);
    Task ApplyAsync(Job job, JsonObject outputs);
}
