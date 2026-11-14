using System.Text.Json;
using System.Text.Json.Nodes;
using Microsoft.EntityFrameworkCore;
using Slopoly.ApiService.Data;
using Slopoly.ApiService.Jobs;
using Slopoly.Contracts;

namespace Slopoly.ApiService.Studio;

/// <summary>Builds job inputs from the pack's current state, so every job carries a complete snapshot.</summary>
public sealed class GenerationService(SlopolyDb db, StudioService studio, JobService jobs, PaletteService palette, Infrastructure.Notifier notifier)
{
    /// <summary>The most references a FLUX.2 klein workflow takes.</summary>
    public const int MaxReferences = 3;

    /// <summary>
    /// Asks for the 3:1 sheet the comfy worker splits into equal thirds (design section 6). Tuned on FLUX.2 klein 4B:
    /// "model sheet" + per-panel wording gives three views; "copy only the style" keeps scene objects out of the sheet.
    /// </summary>
    public const string TurnaroundSheet =
        "Orthographic model sheet of ONE object only: {0}. The object is drawn three times in a row with the same size: " +
        "left panel front elevation, middle panel side elevation, right panel plan view looking straight down from above. " +
        "No perspective, no shadows, white background. Copy only the colours, materials and style of image 1, not its objects.";

    /// <summary>Scene images for the pack's style anchor, referencing the user's style images.</summary>
    public async Task<Job> StyleAnchorAsync(Guid packId, string sceneDescription, int count = 1, long? seed = null)
    {
        var pack = await studio.GetPackAsync(packId);
        var references = await db.StyleReferences.Where(r => r.PackId == packId).OrderBy(r => r.Id)
            .Select(r => r.FileId).Take(MaxReferences).ToListAsync();
        return await jobs.SubmitAsync(JobKinds.Comfy, Workflows.StyleAnchor, packId, null, new JsonObject
        {
            ["prompt"] = Join(pack.StyleText, sceneDescription),
            ["references"] = Ids(references),
            ["count"] = Math.Clamp(count, 1, 4),
            ["seed"] = seed,
        });
    }

    /// <summary>A front/side/top sheet of one asset, referencing the pack's picked anchor images.</summary>
    public async Task<Job> TurnaroundAsync(Guid assetId, string? objectDescription = null, int count = 1, long? seed = null)
    {
        var asset = await studio.GetAssetAsync(assetId);
        var pack = await studio.GetPackAsync(asset.PackId);
        var anchors = await db.ConceptImages
            .Where(c => c.PackId == pack.Id && c.Kind == ConceptKind.Anchor && c.Selection == Selection.Picked)
            .OrderByDescending(c => c.CreatedAt).Select(c => c.FileId).Take(MaxReferences).ToListAsync();
        if (anchors.Count == 0) throw new StudioException("Pick at least one style anchor image of the pack before making turnarounds.");
        return await jobs.SubmitAsync(JobKinds.Comfy, Workflows.Turnaround, pack.Id, assetId, new JsonObject
        {
            // Plain style text ("3D render, studio light") pulls the model back to one perspective view; framed as notes it doesn't.
            ["prompt"] = string.Format(TurnaroundSheet, objectDescription ?? $"{asset.Name}, {asset.Description}")
                         + (string.IsNullOrWhiteSpace(pack.StyleText) ? "" : $" Style notes for colours and materials only: {pack.StyleText.Trim()}"),
            ["references"] = Ids(anchors),
            ["count"] = Math.Clamp(count, 1, 4),
            ["seed"] = seed,
        });
    }

    /// <summary>More images like a concept: its generation job again with a fresh random seed. New images start undecided.</summary>
    public async Task<Job> MoreVariantsAsync(Guid conceptImageId, int count)
    {
        var concept = await db.ConceptImages.FindAsync(conceptImageId) ?? throw StudioException.NotFound("Concept image");
        var source = concept.JobId is { } jobId ? await db.Jobs.FindAsync(jobId) : null;
        if (source is null) throw new StudioException("This image has no generation job to repeat.");
        var inputs = source.Inputs.DeepClone().AsObject();
        inputs["seed"] = null;
        inputs["count"] = Math.Clamp(count, 1, 4);
        return await jobs.SubmitAsync(source.Kind, source.Operation, source.PackId, source.AssetId, inputs);
    }

    /// <summary>Part masks (and their colours) in each view of a turnaround.</summary>
    public async Task<Job> SegmentAsync(Guid conceptImageId, IReadOnlyCollection<string> parts)
    {
        var concept = await db.ConceptImages.FindAsync(conceptImageId) ?? throw StudioException.NotFound("Concept image");
        if (concept.Kind != ConceptKind.Turnaround) throw new StudioException("Only turnaround images can be segmented.");
        if (concept.Selection == Selection.Rejected) throw new StudioException("This turnaround was rejected by the user.");
        var names = parts.Select(p => p.Trim()).Where(p => p.Length > 0).Distinct().ToList();
        if (names.Count == 0) throw new StudioException("Name at least one part to segment.");
        return await jobs.SubmitAsync(JobKinds.Comfy, Workflows.SegmentParts, concept.PackId, concept.AssetId, new JsonObject
        {
            ["conceptImageId"] = concept.Id,
            ["image"] = concept.FileId,
            ["views"] = JsonSerializer.SerializeToNode(concept.Views, Broker.Json),
            ["parts"] = new JsonArray(names.Select(n => (JsonNode)n!).ToArray()),
            ["object"] = concept.AssetId is { } assetId && await db.Assets.FindAsync(assetId) is { } asset ? asset.Name : "object",
        });
    }

    /// <summary>Stores a new immutable program version, makes it current and queues its build.</summary>
    public async Task<(ProgramVersion Version, Job Job)> SubmitProgramAsync(Guid assetId, string source, string note)
    {
        var asset = await studio.GetAssetAsync(assetId);
        if (string.IsNullOrWhiteSpace(source)) throw new StudioException("The program is empty.");
        var number = await db.ProgramVersions.Where(v => v.AssetId == assetId).MaxAsync(v => (int?)v.Number) ?? 0;
        var version = new ProgramVersion { AssetId = assetId, Number = number + 1, Source = source, Note = note };
        db.ProgramVersions.Add(version);
        asset.CurrentProgramVersionId = version.Id;
        await db.SaveChangesAsync();
        await notifier.Changed<ProgramVersion>(version.Id, asset.PackId, assetId);
        return (version, await BuildAsync(asset, version));
    }

    /// <summary>Queues a build of an existing version (e.g. after new masks or palette entries).</summary>
    public async Task<Job> BuildAsync(Asset asset, ProgramVersion version) =>
        await jobs.SubmitAsync(JobKinds.Build, null, asset.PackId, asset.Id, await BuildInputsAsync(asset, version));

    /// <summary>Build inputs: program source, budget, main palette and the picked turnaround with its masks.</summary>
    public async Task<JsonObject> BuildInputsAsync(Asset asset, ProgramVersion version)
    {
        var pack = await studio.GetPackAsync(asset.PackId);
        var turnaround = await db.ConceptImages
            .Where(c => c.AssetId == asset.Id && c.Kind == ConceptKind.Turnaround && c.Selection == Selection.Picked)
            .OrderByDescending(c => c.CreatedAt).FirstOrDefaultAsync();
        var masks = turnaround is null ? [] : await db.PartMasks.Where(m => m.ConceptImageId == turnaround.Id).ToListAsync();
        return new JsonObject
        {
            ["programVersionId"] = version.Id,
            ["source"] = version.Source,
            ["polyBudget"] = pack.PolyBudget,
            ["palette"] = JsonSerializer.SerializeToNode(await palette.MainEntriesAsync(pack.Id), Broker.Json),
            ["turnaround"] = turnaround is null ? null : JsonSerializer.SerializeToNode(new { turnaround.Id, turnaround.FileId, turnaround.Width, turnaround.Height, turnaround.Views }, Broker.Json),
            ["masks"] = JsonSerializer.SerializeToNode(masks, Broker.Json),
        };
    }

    private static string Join(params string?[] parts) => string.Join("\n\n", parts.Where(p => !string.IsNullOrWhiteSpace(p)).Select(p => p!.Trim()));

    private static JsonArray Ids(IEnumerable<Guid> ids) => new(ids.Select(id => (JsonNode)JsonValue.Create(id)!).ToArray());
}
