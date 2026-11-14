using System.Text.Json.Nodes;

namespace Slopoly.Contracts;

/// <summary>SignalR hub contract between the API and the UI.</summary>
public static class Realtime
{
    public const string Path = "/hubs/events";
    /// <summary>Method carrying <see cref="ChangeEvent"/>.</summary>
    public const string Changed = "changed";
    /// <summary>Method carrying <see cref="JobEventMessage"/>.</summary>
    public const string JobEvent = "jobEvent";
}

/// <summary>An entity was created, updated or deleted. <paramref name="Entity"/> is the type name, e.g. "Pack".</summary>
public sealed record ChangeEvent(string Entity, Guid Id, Guid? PackId, Guid? AssetId);

/// <summary>A job changed state or emitted progress/stream output.</summary>
public sealed record JobEventMessage(Guid JobId, string Kind, Guid? PackId, Guid? AssetId, JobState State, string Type, JsonObject? Data);

public static class JobKinds
{
    public const string Comfy = "comfy";
    public const string Build = "build";
    public const string PaletteRender = "palette-render";
    public const string AgentTurn = "agent-turn";
    public static readonly string[] All = [Comfy, Build, PaletteRender, AgentTurn];
}

public static class Workflows
{
    public const string StyleAnchor = "style-anchor";
    public const string Turnaround = "turnaround";
    public const string SegmentParts = "segment-parts";
}
