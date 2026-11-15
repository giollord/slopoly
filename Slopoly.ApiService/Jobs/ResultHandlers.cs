using System.Text.Json;
using System.Text.Json.Nodes;
using Microsoft.EntityFrameworkCore;
using Slopoly.ApiService.Data;
using Slopoly.Contracts;

namespace Slopoly.ApiService.Jobs;

// Output shapes are produced by the workers (see workers/README.md). The UI refreshes from the job's "succeeded"
// broadcast, so handlers only add or update records.

/// <summary>style-anchor and hero: <c>{ images: [ { fileId, width, height, seed } ] }</c>.</summary>
public sealed class ConceptImageResults(SlopolyDb db) : IJobResultHandler
{
    public bool Handles(Job job) => job.Kind == JobKinds.Comfy && job.Operation is Workflows.StyleAnchor or Workflows.Hero;

    public async Task ApplyAsync(Job job, JsonObject outputs)
    {
        var kind = job.Operation == Workflows.Hero ? ConceptKind.Hero : ConceptKind.Anchor;
        // Heroes join the job's variant, or the asset's default variant (jobs queued before variants existed).
        var variantId = kind != ConceptKind.Hero ? null
            : job.Inputs["variantId"]?.GetValue<Guid?>() ?? (await db.Assets.FindAsync(job.AssetId))?.DefaultVariantId;
        foreach (var image in outputs["images"]?.AsArray() ?? [])
        {
            db.ConceptImages.Add(new ConceptImage
            {
                PackId = job.PackId ?? throw new InvalidOperationException("Image jobs need a pack."),
                AssetId = job.AssetId,
                VariantId = variantId,
                JobId = job.Id,
                Kind = kind,
                FileId = image!["fileId"]!.GetValue<Guid>(),
                Width = image["width"]?.GetValue<int>() ?? 0,
                Height = image["height"]?.GetValue<int>() ?? 0,
                Seed = image["seed"]?.GetValue<long>(),
            });
        }
    }
}

/// <summary>
/// views: <c>{ frontYaw, front, views: [ { view, fileId, maskFileId, width, height } ] }</c>. The new views replace the
/// hero's old ones (and their masks); the hero keeps the front and the seed.
/// </summary>
public sealed class ViewsResults(SlopolyDb db) : IJobResultHandler
{
    public bool Handles(Job job) => job.Kind == JobKinds.Comfy && job.Operation == Workflows.Views;

    public async Task ApplyAsync(Job job, JsonObject outputs)
    {
        if (await db.ConceptImages.FindAsync(job.Inputs["heroId"]!.GetValue<Guid>()) is not { } hero) return;
        var old = db.ConceptImages.Where(c => c.SourceConceptId == hero.Id && c.Kind == ConceptKind.View);
        await db.PartMasks.Where(m => old.Any(v => v.Id == m.ConceptImageId)).ExecuteDeleteAsync();
        await old.ExecuteDeleteAsync();
        hero.FrontYaw = outputs["frontYaw"]?.GetValue<double>();
        hero.Front = outputs["front"]?.GetValue<string>();
        hero.ViewsSeed = job.Inputs["seed"]?.GetValue<long>();
        foreach (var view in outputs["views"]?.AsArray() ?? [])
        {
            db.ConceptImages.Add(new ConceptImage
            {
                PackId = hero.PackId,
                AssetId = hero.AssetId,
                VariantId = hero.VariantId,
                JobId = job.Id,
                Kind = ConceptKind.View,
                View = view!["view"]!.GetValue<string>(),
                SourceConceptId = hero.Id,
                FileId = view["fileId"]!.GetValue<Guid>(),
                MaskFileId = view["maskFileId"]?.GetValue<Guid>(),
                Width = view["width"]?.GetValue<int>() ?? 0,
                Height = view["height"]?.GetValue<int>() ?? 0,
            });
        }
    }
}

/// <summary>
/// segment-parts: <c>{ masks: [ { conceptImageId, part, view, fileId, bounds, area, colors } ], missing: [ { part,
/// view, reason } ] }</c>, one mask per view and part, including each view's <c>object</c> silhouette.
/// </summary>
public sealed class SegmentationResults(SlopolyDb db) : IJobResultHandler
{
    public bool Handles(Job job) => job.Kind == JobKinds.Comfy && job.Operation == Workflows.SegmentParts;

    public async Task ApplyAsync(Job job, JsonObject outputs)
    {
        // A new segmentation of the same views replaces the previous masks.
        var viewIds = (job.Inputs["views"]?.AsArray() ?? []).Select(v => v!["conceptImageId"]!.GetValue<Guid>()).ToList();
        await db.PartMasks.Where(m => viewIds.Contains(m.ConceptImageId)).ExecuteDeleteAsync();
        foreach (var mask in outputs["masks"]?.AsArray() ?? [])
        {
            var parsed = mask.Deserialize<PartMask>(Broker.Json)!;
            parsed.Id = Guid.CreateVersion7();
            parsed.JobId = job.Id;
            db.PartMasks.Add(parsed);
        }
    }
}

/// <summary>build: <c>{ glbFileId, blendFileId, validated, report, paletteEntryIds }</c>.</summary>
public sealed class BuildResults(SlopolyDb db) : IJobResultHandler
{
    public bool Handles(Job job) => job.Kind == JobKinds.Build;

    public async Task ApplyAsync(Job job, JsonObject outputs)
    {
        var versionId = job.Inputs["programVersionId"]!.GetValue<Guid>();
        var version = await db.ProgramVersions.FindAsync(versionId);
        if (version is null) return; // its variant or asset was deleted meanwhile
        var build = new Build
        {
            AssetId = job.AssetId!.Value,
            VariantId = version.VariantId,
            ProgramVersionId = versionId,
            JobId = job.Id,
            GlbFileId = outputs["glbFileId"]?.GetValue<Guid>(),
            BlendFileId = outputs["blendFileId"]?.GetValue<Guid>(),
            Validated = outputs["validated"]?.GetValue<bool>() ?? false,
            Report = outputs["report"]?.DeepClone().AsObject(),
            PaletteEntryIds = outputs["paletteEntryIds"]?.Deserialize<List<Guid>>(Broker.Json) ?? [],
        };
        db.Builds.Add(build);
        var variant = await db.AssetVariants.FindAsync(version.VariantId);
        if (variant is null || variant.CurrentProgramVersionId != versionId) return;
        variant.Status = build.Validated ? AssetStatus.Validated : AssetStatus.Built;
        if (await db.Assets.FindAsync(build.AssetId) is { } asset)
        {
            var others = await db.AssetVariants.Where(v => v.AssetId == asset.Id && v.Id != variant.Id).Select(v => v.Status).ToListAsync();
            asset.Status = others.Append(variant.Status).Max();
        }
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

/// <summary>agent-turn: <c>{ sessionId }</c>; keeps the chat's Claude Code session for the next turn (the
/// <c>session</c> stream event already stored it; see <see cref="JobEventApplier"/>).</summary>
public sealed class AgentTurnResults(SlopolyDb db) : IJobResultHandler
{
    public bool Handles(Job job) => job.Kind == JobKinds.AgentTurn;

    public async Task ApplyAsync(Job job, JsonObject outputs)
    {
        if (outputs["sessionId"]?.GetValue<string>() is { } session && await db.Chats.FindAsync(job.ChatId) is { } chat)
            chat.SessionId = session;
    }
}
