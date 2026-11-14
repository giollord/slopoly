using System.Text.Json.Nodes;
using Slopoly.ApiService.Data;
using Slopoly.ApiService.Infrastructure;
using Slopoly.ApiService.Studio;
using Slopoly.Contracts;

namespace Slopoly.ApiService.Jobs;

/// <summary>Job submission, cancel and retry. The row in SQLite is the record; the broker only dispatches.</summary>
public sealed class JobService(SlopolyDb db, Broker broker, Notifier notifier, ILogger<JobService> logger)
{
    public const string DispatchFailed = "dispatch_failed";

    public async Task<Job> GetAsync(Guid id) => await db.Jobs.FindAsync(id) ?? throw StudioException.NotFound("Job");

    public async Task<Job> SubmitAsync(string kind, string? operation, Guid? packId, Guid? assetId, JsonObject inputs)
    {
        if (!JobKinds.All.Contains(kind)) throw new StudioException($"Unknown job kind \"{kind}\".");
        var job = new Job { Kind = kind, Operation = operation, PackId = packId, AssetId = assetId, Inputs = inputs };
        db.Jobs.Add(job);
        await db.SaveChangesAsync();
        await DispatchAsync(job, "queued");
        return job;
    }

    public async Task<Job> CancelAsync(Guid id)
    {
        var job = await GetAsync(id);
        if (job.State is not (JobState.Queued or JobState.Running))
            throw new StudioException($"The job is {job.State.ToString().ToLowerInvariant()} and can't be cancelled.", StatusCodes.Status409Conflict);
        job.State = JobState.Cancelled;
        job.FinishedAt = DateTimeOffset.UtcNow;
        await db.SaveChangesAsync();
        try { await broker.PublishCancelAsync(id); }
        catch (Exception ex) { logger.LogWarning(ex, "Cancel of job {JobId} not broadcast; workers will skip it by state", id); }
        await notifier.JobEvent(job, "cancelled");
        return job;
    }

    public async Task<Job> RetryAsync(Guid id)
    {
        var job = await GetAsync(id);
        if (job.State is not (JobState.Failed or JobState.Cancelled))
            throw new StudioException($"Only failed or cancelled jobs can be retried; this one is {job.State.ToString().ToLowerInvariant()}.", StatusCodes.Status409Conflict);
        job.State = JobState.Queued;
        job.Error = job.ErrorCode = null;
        job.Outputs = null;
        job.Progress = null;
        job.StartedAt = job.FinishedAt = null;
        await db.SaveChangesAsync();
        await DispatchAsync(job, "retried");
        return job;
    }

    private async Task DispatchAsync(Job job, string eventType)
    {
        try
        {
            await broker.PublishJobAsync(new JobMessage(job.Id, job.Kind, job.Operation, job.PackId, job.AssetId, job.Inputs));
        }
        catch (Exception ex)
        {
            logger.LogError(ex, "Job {JobId} could not be dispatched", job.Id);
            job.State = JobState.Failed;
            job.Error = $"The job could not be dispatched to the broker: {ex.Message}";
            job.ErrorCode = DispatchFailed;
            job.FinishedAt = DateTimeOffset.UtcNow;
            await db.SaveChangesAsync();
            eventType = "failed";
        }
        await notifier.JobEvent(job, eventType);
    }
}
