using System.Net;
using System.Net.Http.Json;
using System.Text.Json.Nodes;
using Microsoft.AspNetCore.SignalR.Client;
using RabbitMQ.Client;
using Slopoly.ApiService.Endpoints;
using Slopoly.ApiService.Jobs;
using Slopoly.Contracts;
using static Slopoly.Tests.Api.ApiFixture;

namespace Slopoly.Tests.Api;

/// <summary>generation-jobs scenarios on the API side (tasks 3.1-3.3).</summary>
public sealed class JobQueueTests
{
    [Test]
    public async Task TopologyExistsAfterStart()
    {
        await using var channel = await Rabbit.CreateChannelAsync();
        foreach (var exchange in new[] { Broker.JobsExchange, Broker.EventsExchange, Broker.ControlExchange })
            await channel.ExchangeDeclarePassiveAsync(exchange);
        foreach (var kind in JobKinds.All)
            await channel.QueueDeclarePassiveAsync(Broker.JobQueue(kind));
        await channel.QueueDeclarePassiveAsync(Broker.ApiEventsQueue);
    }

    [Test]
    public async Task JobsAreRoutedByKind()
    {
        var pack = await CreatePackAsync();
        var image = await ReadAsync<Job>(await Client().PostAsJsonAsync($"/api/packs/{pack.Id}/generate", new GenerateRequest(Workflows.StyleAnchor, null, "scene"), Json));
        var chat = await SendChatAsync(pack.Id, "hello");
        Assert.That((await TakeJobAsync(JobKinds.Comfy, image.Id)).Operation, Is.EqualTo(Workflows.StyleAnchor));
        Assert.That((await TakeJobAsync(JobKinds.AgentTurn, chat.Id)).Inputs["message"]!.GetValue<string>(), Is.EqualTo("hello"));
    }

    [Test]
    public async Task LifecycleIsBroadcastAndDuplicateResultsIgnored()
    {
        var pack = await CreatePackAsync();
        await using var hub = await HubAsync();
        var seen = new List<(string Type, JobState State)>();
        var job = await SendChatAsync(pack.Id, "hi");
        hub.On<JobEventMessage>(Realtime.JobEvent, e => { if (e.JobId == job.Id) lock (seen) seen.Add((e.Type, e.State)); });
        await TakeJobAsync(JobKinds.AgentTurn, job.Id);

        await PublishEventAsync(JobKinds.AgentTurn, job.Id, "started");
        await PublishEventAsync(JobKinds.AgentTurn, job.Id, "progress", progress: 0.5);
        await PublishEventAsync(JobKinds.AgentTurn, job.Id, "stream", data: new JsonObject { ["text"] = "Hello" });
        await PublishEventAsync(JobKinds.AgentTurn, job.Id, "succeeded", new JsonObject { ["sessionId"] = "s-1" });
        await PublishEventAsync(JobKinds.AgentTurn, job.Id, "succeeded", new JsonObject { ["sessionId"] = "s-2" });
        await WaitForJobAsync(job.Id, j => j.State == JobState.Succeeded);
        await Task.Delay(300);

        lock (seen)
            Assert.That(seen, Is.EqualTo(new[]
            {
                ("started", JobState.Running), ("progress", JobState.Running), ("stream", JobState.Running), ("succeeded", JobState.Succeeded),
            }));
        var chat = await ReadAsync<Chat>(await Client().GetAsync($"/api/chats/{job.ChatId}"));
        Assert.That(chat.SessionId, Is.EqualTo("s-1"));
        var events = await ReadAsync<List<JobEvent>>(await Client().GetAsync($"/api/jobs/{job.Id}/events"));
        Assert.That(events.Select(e => e.Type), Is.EqualTo(new[] { "started", "stream", "succeeded" }));
    }

    [Test]
    public async Task RedeliveryCountsAnAttempt()
    {
        var pack = await CreatePackAsync();
        var job = await SendChatAsync(pack.Id, "hi");
        await TakeJobAsync(JobKinds.AgentTurn, job.Id);
        await PublishEventAsync(JobKinds.AgentTurn, job.Id, "started");
        await PublishEventAsync(JobKinds.AgentTurn, job.Id, "started");
        var running = await WaitForJobAsync(job.Id, j => j.Attempt == 2);
        Assert.That(running.State, Is.EqualTo(JobState.Running));
    }

    [Test]
    public async Task CancelBroadcastsControlAndIgnoresLateResults()
    {
        await using var channel = await Rabbit.CreateChannelAsync();
        var control = (await channel.QueueDeclareAsync(exclusive: true)).QueueName;
        await channel.QueueBindAsync(control, Broker.ControlExchange, "");

        var pack = await CreatePackAsync();
        var job = await SendChatAsync(pack.Id, "hi");
        await TakeJobAsync(JobKinds.AgentTurn, job.Id);
        await PublishEventAsync(JobKinds.AgentTurn, job.Id, "started");
        await WaitForJobAsync(job.Id, j => j.State == JobState.Running);

        var cancelled = await ReadAsync<Job>(await Client().PostAsync($"/api/jobs/{job.Id}/cancel", null));
        Assert.That(cancelled.State, Is.EqualTo(JobState.Cancelled));
        var message = await channel.BasicGetAsync(control, autoAck: true);
        Assert.That(System.Text.Encoding.UTF8.GetString(message!.Body.Span), Does.Contain(job.Id.ToString()));

        await PublishEventAsync(JobKinds.AgentTurn, job.Id, "succeeded", new JsonObject { ["sessionId"] = "late" });
        await Task.Delay(500);
        var after = await ReadAsync<Job>(await Client().GetAsync($"/api/jobs/{job.Id}"));
        Assert.That(after.State, Is.EqualTo(JobState.Cancelled));
        Assert.That(after.Outputs, Is.Null);
    }

    [Test]
    public async Task CancelledQueuedJobIsVisibleToWorkersAndCanBeRetried()
    {
        var pack = await CreatePackAsync();
        var job = await SendChatAsync(pack.Id, "hi");
        await ReadAsync<Job>(await Client().PostAsync($"/api/jobs/{job.Id}/cancel", null));
        // The worker's check before running a delivered job:
        var state = await ReadAsync<Job>(await WorkerClient().GetAsync($"/worker/jobs/{job.Id}"));
        Assert.That(state.State, Is.EqualTo(JobState.Cancelled));
        await TakeJobAsync(JobKinds.AgentTurn, job.Id);

        var retried = await ReadAsync<Job>(await Client().PostAsync($"/api/jobs/{job.Id}/retry", null));
        Assert.That(retried.State, Is.EqualTo(JobState.Queued));
        await TakeJobAsync(JobKinds.AgentTurn, job.Id);
        var conflict = await Client().PostAsync($"/api/jobs/{job.Id}/retry", null);
        Assert.That(conflict.StatusCode, Is.EqualTo(HttpStatusCode.Conflict));
    }

    [Test]
    public async Task FailureKeepsReadableError()
    {
        var pack = await CreatePackAsync();
        var job = await ReadAsync<Job>(await Client().PostAsJsonAsync($"/api/packs/{pack.Id}/generate", new GenerateRequest(Workflows.StyleAnchor, null, "scene"), Json));
        await TakeJobAsync(JobKinds.Comfy, job.Id);
        await PublishEventAsync(JobKinds.Comfy, job.Id, "started");
        await PublishEventAsync(JobKinds.Comfy, job.Id, "failed", error: "Missing model: flux-2-klein-4b.safetensors");
        var failed = await WaitForJobAsync(job.Id, j => j.State == JobState.Failed);
        Assert.That(failed.Error, Does.Contain("flux-2-klein-4b.safetensors"));
    }

    [Test]
    public async Task WorkerEndpointsNeedTheKey()
    {
        var response = await Client().GetAsync($"/worker/jobs/{Guid.NewGuid()}");
        Assert.That(response.StatusCode, Is.EqualTo(HttpStatusCode.Unauthorized));
    }
}
