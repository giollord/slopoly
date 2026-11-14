using System.Text.Json.Serialization;
using Microsoft.AspNetCore.SignalR.Client;
using Slopoly.Contracts;

namespace Slopoly.Web.Services;

/// <summary>One SignalR connection to the API's event hub, shared by all circuits; components subscribe to it.</summary>
public sealed class LiveEvents(IConfiguration config, ILogger<LiveEvents> logger) : BackgroundService
{
    public event Func<ChangeEvent, Task>? Changed;
    public event Func<JobEventMessage, Task>? JobEvent;

    protected override async Task ExecuteAsync(CancellationToken stoppingToken)
    {
        var api = config["services:apiservice:http:0"] ?? throw new InvalidOperationException("No apiservice endpoint configured.");
        await using var hub = new HubConnectionBuilder()
            .WithUrl(new Uri(new Uri(api), Realtime.Path))
            .WithAutomaticReconnect(new ForeverRetry())
            .AddJsonProtocol(o => o.PayloadSerializerOptions.Converters.Add(new JsonStringEnumConverter()))
            .Build();
        hub.On<ChangeEvent>(Realtime.Changed, e => RaiseAsync(Changed, e));
        hub.On<JobEventMessage>(Realtime.JobEvent, e => RaiseAsync(JobEvent, e));
        while (!stoppingToken.IsCancellationRequested)
        {
            try
            {
                await hub.StartAsync(stoppingToken);
                break;
            }
            catch (Exception ex) when (ex is not OperationCanceledException)
            {
                logger.LogWarning("Event hub not reachable yet: {Message}", ex.Message);
                await Task.Delay(TimeSpan.FromSeconds(2), stoppingToken);
            }
        }
        await Task.Delay(Timeout.Infinite, stoppingToken);
    }

    private async Task RaiseAsync<T>(Func<T, Task>? handlers, T e)
    {
        foreach (var handler in handlers?.GetInvocationList().Cast<Func<T, Task>>() ?? [])
        {
            try { await handler(e); }
            catch (Exception ex) { logger.LogWarning(ex, "Live event handler failed"); }
        }
    }

    private sealed class ForeverRetry : IRetryPolicy
    {
        public TimeSpan? NextRetryDelay(RetryContext context) => TimeSpan.FromSeconds(Math.Min(10, 1 + context.PreviousRetryCount));
    }
}
