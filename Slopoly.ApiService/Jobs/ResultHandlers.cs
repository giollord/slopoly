using System.Text.Json;
using System.Text.Json.Nodes;
using Microsoft.EntityFrameworkCore;
using Slopoly.ApiService.Data;
using Slopoly.Contracts;

namespace Slopoly.ApiService.Jobs;

// Output shapes are produced by the workers (see workers/README.md). The UI refreshes from the job's "succeeded"
// broadcast, so handlers only add or update records.

/// <summary>style-anchor and turnaround: <c>{ images: [ { fileId, width, height, views? } ] }</c>.</summary>
public sealed class ConceptImageResults(SlopolyDb db) : IJobResultHandler
{
    public bool Handles(Job job) => job.Kind == JobKinds.Comfy && job.Operation is Workflows.StyleAnchor or Workflows.Turnaround;

    public Task ApplyAsync(Job job, JsonObject outputs)
    {
        var kind = job.Operation == Workflows.Turnaround ? ConceptKind.Turnaround : ConceptKind.Anchor;
        foreach (var image in outputs["images"]?.AsArray() ?? [])
        {
            db.ConceptImages.Add(new ConceptImage
            {
                PackId = job.PackId ?? throw new InvalidOperationException("Image jobs need a pack."),
                AssetId = job.AssetId,
                JobId = job.Id,
                Kind = kind,
                FileId = image!["fileId"]!.GetValue<Guid>(),
                Width = image["width"]?.GetValue<int>() ?? 0,
                Height = image["height"]?.GetValue<int>() ?? 0,
                Seed = image["seed"]?.GetValue<long>(),
                Views = image["views"]?.Deserialize<Dictionary<string, Rect>>(Broker.Json) ?? [],
            });
        }
        return Task.CompletedTask;
    }
}

/// <summary>segment-parts: <c>{ masks: [ { part, view, fileId, bounds, area, colors } ], missing: [ { part, view } ] }</c>.</summary>
public sealed class SegmentationResults(SlopolyDb db) : IJobResultHandler
{
    public bool Handles(Job job) => job.Kind == JobKinds.Comfy && job.Operation == Workflows.SegmentParts;

    public async Task ApplyAsync(Job job, JsonObject outputs)
    {
        var conceptId = job.Inputs["conceptImageId"]!.GetValue<Guid>();
        // A new segmentation of the same image replaces the previous masks.
        await db.PartMasks.Where(m => m.ConceptImageId == conceptId).ExecuteDeleteAsync();
        foreach (var mask in outputs["masks"]?.AsArray() ?? [])
        {
            var parsed = mask.Deserialize<PartMask>(Broker.Json)!;
            parsed.Id = Guid.CreateVersion7();
            parsed.ConceptImageId = conceptId;
            parsed.JobId = job.Id;
            db.PartMasks.Add(parsed);
        }
    }
}

/// <summary>build: <c>{ glbFileId, validated, report, paletteEntryIds }</c>.</summary>
public sealed class BuildResults(SlopolyDb db) : IJobResultHandler
{
    public bool Handles(Job job) => job.Kind == JobKinds.Build;

    public async Task ApplyAsync(Job job, JsonObject outputs)
    {
        var versionId = job.Inputs["programVersionId"]!.GetValue<Guid>();
        var build = new Build
        {
            AssetId = job.AssetId!.Value,
            ProgramVersionId = versionId,
            JobId = job.Id,
            GlbFileId = outputs["glbFileId"]?.GetValue<Guid>(),
            Validated = outputs["validated"]?.GetValue<bool>() ?? false,
            Report = outputs["report"]?.DeepClone().AsObject(),
            PaletteEntryIds = outputs["paletteEntryIds"]?.Deserialize<List<Guid>>(Broker.Json) ?? [],
        };
        db.Builds.Add(build);
        var asset = await db.Assets.FindAsync(build.AssetId);
        if (asset is not null && asset.CurrentProgramVersionId == versionId)
            asset.Status = build.Validated ? AssetStatus.Validated : AssetStatus.Built;
    }
}

/// <summary>scene: <c>{ glbFileId, report }</c>, stored on the scene.</summary>
public sealed class SceneResults(SlopolyDb db) : IJobResultHandler
{
    public bool Handles(Job job) => job.Kind == JobKinds.Scene;

    public async Task ApplyAsync(Job job, JsonObject outputs)
    {
        if (await db.Scenes.FindAsync(job.Inputs["sceneId"]!.GetValue<Guid>()) is not { } scene) return;
        scene.GlbFileId = outputs["glbFileId"]?.GetValue<Guid>();
        scene.Report = outputs["report"]?.DeepClone().AsObject();
    }
}

/// <summary>agent-turn: <c>{ sessionId }</c>; keeps the pack's Claude Code session for the next turn.</summary>
public sealed class AgentTurnResults(SlopolyDb db) : IJobResultHandler
{
    public bool Handles(Job job) => job.Kind == JobKinds.AgentTurn;

    public async Task ApplyAsync(Job job, JsonObject outputs)
    {
        if (outputs["sessionId"]?.GetValue<string>() is { } session && await db.Packs.FindAsync(job.PackId) is { } pack)
            pack.AgentSessionId = session;
    }
}
