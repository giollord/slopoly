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
    /// <summary>The most references the image workflows take (Qwen-Image-Edit's image 1-3).</summary>
    public const int MaxReferences = 3;

    /// <summary>The hero prompt (design section 1): one whole object, a three-quarter front view, the references' style.</summary>
    public const string HeroImage =
        "ONE object only, whole and centred: {0}. Three-quarter front view from the front-left, slightly from above. " +
        "Plain light grey background, nothing else in the image. Copy only the colours, materials and style of the " +
        "reference images, not their objects.";

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

    /// <summary>Hero images of one asset variant (the default when omitted), referencing the pack's picked anchor images.</summary>
    public async Task<Job> HeroAsync(Guid assetId, string? objectDescription = null, int count = 1, long? seed = null, Guid? variantId = null)
    {
        var asset = await studio.GetAssetAsync(assetId);
        var variant = await studio.VariantOfAsync(assetId, variantId);
        var pack = await studio.GetPackAsync(asset.PackId);
        var anchors = await db.ConceptImages
            .Where(c => c.PackId == pack.Id && c.Kind == ConceptKind.Anchor && c.Selection == Selection.Picked)
            .OrderByDescending(c => c.CreatedAt).Select(c => c.FileId).Take(MaxReferences).ToListAsync();
        if (anchors.Count == 0) throw new StudioException("Pick at least one style anchor image of the pack before making heroes.");
        return await jobs.SubmitAsync(JobKinds.Comfy, Workflows.Hero, pack.Id, assetId, new JsonObject
        {
            // Plain style text ("3D render, studio light") can override the view; framed as notes it doesn't.
            ["prompt"] = string.Format(HeroImage, objectDescription ?? $"{asset.Name}, {asset.Description}")
                         + (string.IsNullOrWhiteSpace(pack.StyleText) ? "" : $" Style notes for colours and materials only: {pack.StyleText.Trim()}"),
            ["references"] = Ids(anchors),
            ["count"] = Math.Clamp(count, 1, 4),
            ["seed"] = seed,
            ["variantId"] = variant.Id,
        });
    }

    /// <summary>
    /// Front, side, top and back views of a picked hero, rendered from its splat (design sections 2-3). With a front
    /// yaw the hero's last views seed is reused, so the splat is the same and only the front changes.
    /// </summary>
    public async Task<Job> ViewsAsync(Guid heroId, double? frontYaw = null)
    {
        var hero = await db.ConceptImages.FindAsync(heroId) ?? throw StudioException.NotFound("Concept image");
        if (hero.Kind != ConceptKind.Hero) throw new StudioException("Views are made from hero images only.");
        if (hero.Selection != Selection.Picked) throw new StudioException("Pick the hero image before making its views.");
        var seed = frontYaw is not null && hero.ViewsSeed is { } same ? same : Random.Shared.NextInt64(1, 1L << 48);
        return await jobs.SubmitAsync(JobKinds.Comfy, Workflows.Views, hero.PackId, hero.AssetId, new JsonObject
        {
            ["heroId"] = hero.Id,
            ["image"] = hero.FileId,
            ["seed"] = seed,
            ["frontYaw"] = frontYaw is { } yaw ? ((yaw % 360) + 360) % 360 : null,
        });
    }

    /// <summary>
    /// New images from a concept's generation with a fresh seed. With a change, the concept itself becomes the first
    /// reference and the change is added to the prompt (Qwen-Image-Edit edits image 1). New images start undecided.
    /// </summary>
    public async Task<Job> ReviseAsync(Guid conceptImageId, string? change, int count)
    {
        var concept = await db.ConceptImages.FindAsync(conceptImageId) ?? throw StudioException.NotFound("Concept image");
        var source = concept.JobId is { } jobId ? await db.Jobs.FindAsync(jobId) : null;
        if (source is null) throw new StudioException("This image has no generation job to repeat.");
        var inputs = source.Inputs.DeepClone().AsObject();
        inputs["seed"] = null;
        if (concept.Kind == ConceptKind.Hero) inputs["variantId"] = concept.VariantId; // the hero may have moved variant
        inputs["count"] = Math.Clamp(count, 1, 4);
        if (!string.IsNullOrWhiteSpace(change))
        {
            inputs["prompt"] = $"{inputs["prompt"]?.GetValue<string>()}\n\nChange from image 1: {change.Trim()}";
            var references = (inputs["references"]?.AsArray() ?? []).Select(r => r!.GetValue<Guid>()).Where(r => r != concept.FileId);
            inputs["references"] = Ids(references.Prepend(concept.FileId).Take(MaxReferences));
        }
        return await jobs.SubmitAsync(source.Kind, source.Operation, source.PackId, source.AssetId, inputs);
    }

    /// <summary>Part masks (and their colours) in each view image of a hero (or of a view's hero).</summary>
    public async Task<Job> SegmentAsync(Guid conceptImageId, IReadOnlyCollection<string> parts)
    {
        var hero = await HeroOfAsync(conceptImageId);
        if (hero.Selection == Selection.Rejected) throw new StudioException("This hero was rejected by the user.");
        var views = await ViewsOfAsync(hero.Id);
        if (views.Count == 0) throw new StudioException("Make the hero's views before segmenting it.");
        var names = parts.Select(p => p.Trim()).Where(p => p.Length > 0 && p != PartMasks.Object).Distinct().ToList();
        if (names.Count == 0) throw new StudioException("Name at least one part to segment.");
        return await jobs.SubmitAsync(JobKinds.Comfy, Workflows.SegmentParts, hero.PackId, hero.AssetId, new JsonObject
        {
            ["heroId"] = hero.Id,
            ["views"] = new JsonArray(views.Select(v => (JsonNode)new JsonObject
            {
                ["conceptImageId"] = v.Id, ["view"] = v.View, ["image"] = v.FileId, ["mask"] = v.MaskFileId,
            }).ToArray()),
            ["parts"] = new JsonArray(names.Select(n => (JsonNode)n!).ToArray()),
        });
    }

    /// <summary>The hero itself, or a view's hero.</summary>
    public async Task<ConceptImage> HeroOfAsync(Guid conceptImageId)
    {
        var concept = await db.ConceptImages.FindAsync(conceptImageId) ?? throw StudioException.NotFound("Concept image");
        if (concept.Kind == ConceptKind.View && concept.SourceConceptId is { } heroId)
            concept = await db.ConceptImages.FindAsync(heroId) ?? throw StudioException.NotFound("Hero image");
        return concept.Kind == ConceptKind.Hero ? concept : throw new StudioException("Only hero images and their views can be segmented.");
    }

    /// <summary>Part masks of one view, or of all views of a hero.</summary>
    public async Task<List<PartMask>> MasksOfAsync(Guid conceptImageId)
    {
        var concept = await db.ConceptImages.FindAsync(conceptImageId) ?? throw StudioException.NotFound("Concept image");
        var ids = concept.Kind == ConceptKind.Hero ? (await ViewsOfAsync(concept.Id)).Select(v => v.Id).ToList() : [concept.Id];
        return await db.PartMasks.Where(m => ids.Contains(m.ConceptImageId)).OrderBy(m => m.Part).ThenBy(m => m.View).ToListAsync();
    }

    /// <summary>A hero's view images, in the order front, side, top, back.</summary>
    public async Task<List<ConceptImage>> ViewsOfAsync(Guid heroId) =>
        (await db.ConceptImages.Where(c => c.SourceConceptId == heroId && c.Kind == ConceptKind.View).ToListAsync())
        .OrderBy(v => Array.IndexOf(ViewNames.All, v.View)).ToList();

    /// <summary>Stores a new immutable program version of a variant (the default when omitted), makes it the
    /// variant's current version and queues its build.</summary>
    public async Task<(ProgramVersion Version, Job Job)> SubmitProgramAsync(Guid assetId, Guid? variantId, string source, string note)
    {
        var asset = await studio.GetAssetAsync(assetId);
        var variant = await studio.VariantOfAsync(assetId, variantId);
        if (string.IsNullOrWhiteSpace(source)) throw new StudioException("The program is empty.");
        var number = await db.ProgramVersions.Where(v => v.VariantId == variant.Id).MaxAsync(v => (int?)v.Number) ?? 0;
        var version = new ProgramVersion { AssetId = assetId, VariantId = variant.Id, Number = number + 1, Source = source, Note = note };
        db.ProgramVersions.Add(version);
        variant.CurrentProgramVersionId = version.Id;
        await db.SaveChangesAsync();
        await notifier.Changed<ProgramVersion>(version.Id, asset.PackId, assetId);
        return (version, await BuildAsync(asset, version));
    }

    /// <summary>A new variant (see <see cref="StudioService.CreateVariantAsync"/>); a copied program is built.</summary>
    public async Task<AssetVariant> CreateVariantAsync(Guid assetId, VariantCreate create)
    {
        var (variant, copied) = await studio.CreateVariantAsync(assetId, create);
        if (copied is not null) await BuildAsync(await studio.GetAssetAsync(assetId), copied);
        return variant;
    }

    /// <summary>Queues a build of an existing version (e.g. after new masks or palette entries).</summary>
    public async Task<Job> BuildAsync(Asset asset, ProgramVersion version) =>
        await jobs.SubmitAsync(JobKinds.Build, null, asset.PackId, asset.Id, await BuildInputsAsync(asset, version));

    /// <summary>Why a build has no views to compare with, when its variant has no picked hero.</summary>
    public const string NoReferenceHero = "no reference hero for this variant";

    /// <summary>Build inputs: program source, budget, the pack's shading, main palette and the views (with masks) of
    /// the version's variant's reference hero.</summary>
    public async Task<JsonObject> BuildInputsAsync(Asset asset, ProgramVersion version)
    {
        var pack = await studio.GetPackAsync(asset.PackId);
        var hero = await db.ConceptImages
            .Where(c => c.VariantId == version.VariantId && c.Kind == ConceptKind.Hero && c.Selection == Selection.Picked)
            .OrderByDescending(c => c.CreatedAt).FirstOrDefaultAsync();
        var views = hero is null ? [] : await ViewsOfAsync(hero.Id);
        var viewIds = views.Select(v => v.Id).ToList();
        var masks = await db.PartMasks.Where(m => viewIds.Contains(m.ConceptImageId)).ToListAsync();
        return new JsonObject
        {
            ["programVersionId"] = version.Id,
            ["variantId"] = version.VariantId,
            ["noViewsReason"] = hero is null ? NoReferenceHero : null,
            ["source"] = version.Source,
            ["polyBudget"] = asset.PolyBudget ?? pack.PolyBudget,
            ["shading"] = new JsonObject
            {
                ["mode"] = pack.ShadingMode.ToString().ToLowerInvariant(),
                ["hardEdgeAngle"] = pack.HardEdgeAngle,
                ["shadeStrength"] = pack.ShadeStrength,
            },
            ["palette"] = JsonSerializer.SerializeToNode(await palette.MainEntriesAsync(pack.Id), Broker.Json),
            ["views"] = JsonSerializer.SerializeToNode(views.Select(v => new { v.Id, v.View, v.FileId, v.Width, v.Height }), Broker.Json),
            ["masks"] = JsonSerializer.SerializeToNode(masks, Broker.Json),
        };
    }

    /// <summary>Creates or replaces a scene (matched by name within the pack) and queues its build.</summary>
    public async Task<Scene> SaveSceneAsync(Guid packId, SceneEdit edit)
    {
        await studio.GetPackAsync(packId);
        var name = string.IsNullOrWhiteSpace(edit.Name) ? throw new StudioException("A scene needs a name.") : edit.Name.Trim();
        var names = new HashSet<string>();
        foreach (var p in edit.Placements)
        {
            if (string.IsNullOrWhiteSpace(p.Name) || !names.Add(p.Name))
                throw new StudioException($"Placement names must be unique and non-empty (\"{p.Name}\").");
            if (p.At is not { Length: 3 } || p.Rot is not (null or { Length: 3 }) || p.Scale <= 0)
                throw new StudioException($"Placement \"{p.Name}\" needs at = [x, y, z], optional rot = [x, y, z] and a positive scale.");
        }
        var scene = await db.Scenes.FirstOrDefaultAsync(s => s.PackId == packId && s.Name == name);
        if (scene is null) db.Scenes.Add(scene = new Scene { PackId = packId, Name = name });
        scene.Description = edit.Description ?? scene.Description;
        scene.Placements = edit.Placements;
        if (edit.Versions is not null) scene.Versions = edit.Versions.Where(v => v.ProgramVersionId is not null).ToList();
        scene.UpdatedAt = DateTimeOffset.UtcNow;
        var inputs = await SceneInputsAsync(scene);
        await db.SaveChangesAsync();
        await notifier.Changed<Scene>(scene.Id, packId);
        if (scene.Placements.Count > 0) await jobs.SubmitAsync(JobKinds.Scene, null, packId, null, inputs);
        else (scene.GlbFileId, scene.Report) = (null, null);
        await db.SaveChangesAsync();
        return scene;
    }

    /// <summary>Scene build inputs: each placement with the GLB of the latest build of the version chosen for its
    /// asset variant (the variant's current version unless the scene names one).</summary>
    private async Task<JsonObject> SceneInputsAsync(Scene scene)
    {
        var placements = new JsonArray();
        foreach (var p in scene.Placements)
        {
            var asset = await db.Assets.FirstOrDefaultAsync(a => a.Id == p.AssetId && a.PackId == scene.PackId)
                        ?? throw new StudioException($"Placement \"{p.Name}\" refers to an asset that is not in this pack.");
            var variant = await db.AssetVariants.FindAsync(p.VariantId ?? asset.DefaultVariantId);
            if (variant is null || variant.AssetId != asset.Id)
                throw new StudioException($"Placement \"{p.Name}\" refers to a variant that \"{asset.Name}\" doesn't have.");
            var versionId = scene.Versions.FirstOrDefault(v => v.AssetId == asset.Id && v.VariantId == variant.Id)?.ProgramVersionId
                            ?? variant.CurrentProgramVersionId;
            var version = versionId is null ? null : await db.ProgramVersions.FindAsync(versionId);
            if (version is null || version.VariantId != variant.Id)
                throw new StudioException($"\"{asset.Name}\" has no build yet: its variant \"{variant.Name}\" has no program version.");
            var glb = await db.Builds
                          .Where(b => b.ProgramVersionId == version.Id && b.GlbFileId != null)
                          .OrderByDescending(b => b.CreatedAt).Select(b => b.GlbFileId).FirstOrDefaultAsync()
                      ?? throw new StudioException($"\"{asset.Name}\" ({variant.Name}) has no build of v{version.Number} yet.");
            placements.Add(new JsonObject
            {
                ["name"] = p.Name,
                ["glbFileId"] = glb,
                ["at"] = JsonSerializer.SerializeToNode(p.At),
                ["rot"] = JsonSerializer.SerializeToNode(p.Rot ?? [0, 0, 0]),
                ["scale"] = p.Scale,
            });
        }
        return new JsonObject { ["sceneId"] = scene.Id, ["placements"] = placements };
    }

    private static string Join(params string?[] parts) => string.Join("\n\n", parts.Where(p => !string.IsNullOrWhiteSpace(p)).Select(p => p!.Trim()));

    private static JsonArray Ids(IEnumerable<Guid> ids) => new(ids.Select(id => (JsonNode)JsonValue.Create(id)!).ToArray());
}
