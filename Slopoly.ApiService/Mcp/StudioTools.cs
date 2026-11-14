using System.ComponentModel;
using System.Text.Json.Nodes;
using Microsoft.EntityFrameworkCore;
using ModelContextProtocol.Protocol;
using ModelContextProtocol.Server;
using Slopoly.ApiService.Data;
using Slopoly.ApiService.Infrastructure;
using Slopoly.ApiService.Jobs;
using Slopoly.ApiService.Studio;
using Slopoly.Contracts;

namespace Slopoly.ApiService.Mcp;

/// <summary>
/// The agent's tool surface (design section 10): thin wrappers over the services the REST API uses, so changes reach
/// the UI through the same notifications. Results are ids and numbers; only <c>view_image</c> returns image data.
/// </summary>
[McpServerToolType]
public sealed class StudioTools(StudioService studio, GenerationService generation, PaletteService palette, JobService jobs,
    SlopolyDb db, FileStore files)
{
    public sealed record PackOverview(Pack Pack, List<Asset> Assets, List<StyleReference> StyleReferences, List<Job> ActiveJobs);

    public sealed record MaskInfo(Guid Id, string Part, string View, Guid FileId, Rect Bounds, int Area);

    public sealed record Segmentation(Guid ConceptImageId, int Width, int Height, Dictionary<string, Rect> Views,
        List<MaskInfo> Masks, JsonNode? Missing);

    public sealed record PartColors(string Part, string View, List<MeasuredColor> Colors);

    public sealed record BuildReport(Guid BuildId, Guid ProgramVersionId, int ProgramVersion, bool Validated, Guid? GlbFileId,
        JsonObject? Report);

    [McpServerTool(Name = "get_pack", ReadOnly = true), Description("The pack (instructions, style text, polygon budget), its assets, style reference file ids and queued or running jobs.")]
    public async Task<PackOverview> GetPack(Guid packId)
    {
        var pack = await studio.GetPackAsync(packId);
        return new(pack,
            await db.Assets.Where(a => a.PackId == packId).OrderBy(a => a.CreatedAt).ToListAsync(),
            await db.StyleReferences.Where(r => r.PackId == packId).ToListAsync(),
            await db.Jobs.Where(j => j.PackId == packId && (j.State == JobState.Queued || j.State == JobState.Running)).ToListAsync());
    }

    [McpServerTool(Name = "update_style"), Description("Updates the pack's style text and/or general instructions (null keeps a value).")]
    public Task<Pack> UpdateStyle(Guid packId, string? styleText = null, string? instructions = null) =>
        studio.UpdatePackAsync(packId, new PackEdit(null, instructions, styleText, null));

    [McpServerTool(Name = "create_asset"), Description("Creates an asset (one object of the pack) and returns it.")]
    public Task<Asset> CreateAsset(Guid packId, string name, string description) => studio.CreateAssetAsync(packId, name, description);

    [McpServerTool(Name = "start_job"), Description("""
        Starts a generation job and returns it (poll get_job). operation:
        - "style-anchor": packId, description = scene description; uses the pack style text and style references.
        - "turnaround": assetId (needs a picked style anchor), optional description of the object.
        - "segment-parts": conceptImageId (a picked turnaround) and parts = part names from the manifest.
        count (1-4) images per run; seed optional.
        """)]
    public Task<Job> StartJob(string operation, Guid? packId = null, Guid? assetId = null, string? description = null,
        Guid? conceptImageId = null, List<string>? parts = null, int count = 1, long? seed = null) => operation switch
    {
        Workflows.StyleAnchor => generation.StyleAnchorAsync(packId ?? throw new StudioException("style-anchor needs packId."), description ?? "", count, seed),
        Workflows.Turnaround => generation.TurnaroundAsync(assetId ?? throw new StudioException("turnaround needs assetId."), description, count, seed),
        Workflows.SegmentParts => generation.SegmentAsync(conceptImageId ?? throw new StudioException("segment-parts needs conceptImageId."),
            parts ?? throw new StudioException("segment-parts needs parts.")),
        _ => throw new StudioException($"Unknown operation \"{operation}\" (style-anchor, turnaround, segment-parts)."),
    };

    [McpServerTool(Name = "get_job", ReadOnly = true), Description("A job's state, progress, error and outputs.")]
    public Task<Job> GetJob(Guid jobId) => jobs.GetAsync(jobId);

    [McpServerTool(Name = "cancel_job"), Description("Cancels a queued or running job.")]
    public Task<Job> CancelJob(Guid jobId) => jobs.CancelAsync(jobId);

    [McpServerTool(Name = "retry_job"), Description("Queues a failed or cancelled job again.")]
    public Task<Job> RetryJob(Guid jobId) => jobs.RetryAsync(jobId);

    [McpServerTool(Name = "list_concepts", ReadOnly = true), Description("Concept images the user has not rejected (style anchors and turnarounds), with selection (Picked/None), size and view rectangles. Optionally for one asset.")]
    public Task<List<ConceptImage>> ListConcepts(Guid packId, Guid? assetId = null) => studio.ListConceptsAsync(packId, assetId);

    [McpServerTool(Name = "more_variants"), Description("Generates more images like a concept (its generation again with a new seed, 1-4 images) and returns the job. Use when the user asks for more options.")]
    public Task<Job> MoreVariants(Guid conceptImageId, int count = 2) => generation.MoreVariantsAsync(conceptImageId, count);

    [McpServerTool(Name = "get_segmentation", ReadOnly = true), Description("Part masks of a turnaround: per part and view the mask file id, bounds in image pixels and area, plus parts that were not found.")]
    public async Task<Segmentation> GetSegmentation(Guid conceptImageId)
    {
        var concept = await db.ConceptImages.FindAsync(conceptImageId) ?? throw StudioException.NotFound("Concept image");
        var masks = await db.PartMasks.Where(m => m.ConceptImageId == conceptImageId).OrderBy(m => m.Part).ThenBy(m => m.View).ToListAsync();
        var job = masks.Count > 0 ? await db.Jobs.FindAsync(masks[0].JobId) : null;
        var missing = job?.Outputs?["missing"]?.DeepClone();
        return new(concept.Id, concept.Width, concept.Height, concept.Views,
            masks.Select(m => new MaskInfo(m.Id, m.Part, m.View, m.FileId, m.Bounds, m.Area)).ToList(), missing);
    }

    [McpServerTool(Name = "get_part_colors", ReadOnly = true), Description("Measured dominant colours (hex, coverage) per part and view of a segmented turnaround: starting points for palette entries.")]
    public async Task<List<PartColors>> GetPartColors(Guid conceptImageId) =>
        (await db.PartMasks.Where(m => m.ConceptImageId == conceptImageId).OrderBy(m => m.Part).ThenBy(m => m.View).ToListAsync())
        .Select(m => new PartColors(m.Part, m.View, m.Colors)).ToList();

    [McpServerTool(Name = "get_palette", ReadOnly = true), Description("The pack's main palette entries (role, kind, slot, colours) and its variants. Model only with main-palette roles.")]
    public Task<PaletteView> GetPalette(Guid packId) => palette.GetAsync(packId);

    [McpServerTool(Name = "upsert_palette_entries"), Description("Adds or recolours main palette entries, matched by role. Name roles by usage (\"wall base\", \"leaf 1\"); use a colour name only for a colour that stays the same in every palette. kind: Solid, or Gradient with color2.")]
    public Task<List<PaletteEntry>> UpsertPaletteEntries(Guid packId, List<PaletteEntryEdit> entries) => palette.UpsertEntriesAsync(packId, entries);

    [McpServerTool(Name = "upsert_palette_variant"), Description("Creates or updates a named palette variant (only when the user asks). Roles not given keep the main colour.")]
    public Task<VariantView> UpsertPaletteVariant(Guid packId, string name, List<VariantColorEdit> colors) => palette.UpsertVariantAsync(packId, name, colors);

    [McpServerTool(Name = "save_manifest"), Description("""
        Stores the asset's part manifest: {"symmetry": ["x"], "parts": [{"name", "parent", "primitive", "mirror",
        "connections": [{"to", "type": "fixed"|"rotate"|"slide", "axis"}]}]}. Exactly one part has no parent.
        """)]
    public Task<Manifest> SaveManifest(Guid assetId, JsonObject manifest) => studio.SaveManifestAsync(assetId, manifest);

    [McpServerTool(Name = "submit_program"), Description("Stores a new slopoly_model part program version for the asset, makes it current and starts its build job (poll get_job, then get_build_report).")]
    public async Task<Job> SubmitProgram(Guid assetId, string source, string? note = null) =>
        (await generation.SubmitProgramAsync(assetId, source, note ?? "")).Job;

    [McpServerTool(Name = "get_build_report", ReadOnly = true), Description("The latest build of the asset (or a given build): validated flag, validator results, silhouette scores per part and view, colour likeness and palette roles.")]
    public async Task<BuildReport> GetBuildReport(Guid assetId, Guid? buildId = null)
    {
        var build = await db.Builds.Where(b => b.AssetId == assetId && (buildId == null || b.Id == buildId))
            .OrderByDescending(b => b.CreatedAt).FirstOrDefaultAsync() ?? throw StudioException.NotFound("Build");
        var version = await db.ProgramVersions.FindAsync(build.ProgramVersionId);
        return new(build.Id, build.ProgramVersionId, version?.Number ?? 0, build.Validated, build.GlbFileId, build.Report);
    }

    [McpServerTool(Name = "view_image", ReadOnly = true), Description("Returns an image file (concept, mask, palette) for viewing. Costly: use only when numbers aren't enough.")]
    public async Task<CallToolResult> ViewImage(Guid fileId)
    {
        var file = await db.Files.FindAsync(fileId) ?? throw StudioException.NotFound("File");
        if (file.ContentType?.StartsWith("image/") != true) throw new StudioException($"File {fileId} is not an image ({file.ContentType}).");
        return new() { Content = [ImageContentBlock.FromBytes(await File.ReadAllBytesAsync(files.PathOf(fileId)), file.ContentType)] };
    }
}
