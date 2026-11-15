using Microsoft.AspNetCore.Components;
using MudBlazor;
using Slopoly.Contracts;
using Slopoly.Web.Services;

namespace Slopoly.Web.Components.Shared;

/// <summary>
/// Base for components that show API data: loads on parameter changes, reloads when a related change or job event
/// arrives, and shows API errors as snackbars.
/// </summary>
public abstract class LiveComponent : ComponentBase, IDisposable
{
    [Inject] protected StudioApi Api { get; set; } = null!;
    [Inject] protected LiveEvents Live { get; set; } = null!;
    [Inject] protected ISnackbar Snackbar { get; set; } = null!;

    protected abstract Task LoadAsync();

    /// <summary>Whether a change or job event of this pack/asset concerns the component.</summary>
    protected abstract bool Concerns(Guid? packId, Guid? assetId);

    /// <summary>Whether a job event concerns the component; by default, when its pack or asset does.</summary>
    protected virtual bool ConcernsJob(JobEventMessage e) => Concerns(e.PackId, e.AssetId);

    /// <summary>Job events of interest; by default lifecycle events (not progress or stream ticks) reload.</summary>
    protected virtual Task OnJobEventAsync(JobEventMessage e) =>
        e.Type is "progress" or "stream" ? Task.CompletedTask : LoadAsync();

    protected override void OnInitialized()
    {
        Live.Changed += OnChanged;
        Live.JobEvent += OnJobEvent;
    }

    protected override Task OnParametersSetAsync() => Try(LoadAsync);

    private Task OnChanged(ChangeEvent e) =>
        Concerns(e.PackId, e.AssetId) ? InvokeAsync(() => Try(async () => { await LoadAsync(); StateHasChanged(); })) : Task.CompletedTask;

    private Task OnJobEvent(JobEventMessage e) =>
        ConcernsJob(e) ? InvokeAsync(() => Try(async () => { await OnJobEventAsync(e); StateHasChanged(); })) : Task.CompletedTask;

    /// <summary>Runs an action; API errors become an error snackbar.</summary>
    protected async Task Try(Func<Task> action)
    {
        try { await action(); }
        catch (ApiException ex) { Snackbar.Add(ex.Message, Severity.Error); }
        catch (HttpRequestException ex) { Snackbar.Add($"The API is not reachable: {ex.Message}", Severity.Error); }
    }

    public void Dispose()
    {
        Live.Changed -= OnChanged;
        Live.JobEvent -= OnJobEvent;
        GC.SuppressFinalize(this);
    }
}
