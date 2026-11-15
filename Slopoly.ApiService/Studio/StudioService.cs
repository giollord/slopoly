using System.Text.Json.Nodes;
using Microsoft.EntityFrameworkCore;
using Slopoly.ApiService.Data;
using Slopoly.ApiService.Infrastructure;
using Slopoly.Contracts;

namespace Slopoly.ApiService.Studio;

/// <summary>A request the API refuses; mapped to 400/404/409 for REST and to a tool error for MCP. <see cref="Code"/>
/// lets the UI react to a specific refusal.</summary>
public sealed class StudioException(string message, int status = StatusCodes.Status400BadRequest, string? code = null) : Exception(message)
{
    public int Status { get; } = status;
    public string? Code { get; } = code;
    public static StudioException NotFound(string what) => new($"{what} not found.", StatusCodes.Status404NotFound);
}

/// <summary>Pack, asset, variant, concept and program operations shared by the REST endpoints and the MCP tools.</summary>
public sealed class StudioService(SlopolyDb db, FileStore files, Notifier notifier, Jobs.JobService jobs)
{
    public const string DefaultVariantName = "default";

    public async Task<Pack> GetPackAsync(Guid id) => await db.Packs.FindAsync(id) ?? throw StudioException.NotFound("Pack");

    public async Task<Asset> GetAssetAsync(Guid id) => await db.Assets.FindAsync(id) ?? throw StudioException.NotFound("Asset");

    public async Task<AssetVariant> GetVariantAsync(Guid id) => await db.AssetVariants.FindAsync(id) ?? throw StudioException.NotFound("Variant");

    /// <summary>The asset's variant with this id, or its default variant when none is given.</summary>
    public async Task<AssetVariant> VariantOfAsync(Guid assetId, Guid? variantId)
    {
        var asset = await GetAssetAsync(assetId);
        var variant = await db.AssetVariants.FindAsync(variantId ?? asset.DefaultVariantId);
        return variant is not null && variant.AssetId == assetId ? variant : throw StudioException.NotFound("Variant of this asset");
    }

    public Task<List<AssetVariant>> VariantsAsync(Guid assetId) =>
        db.AssetVariants.Where(v => v.AssetId == assetId).OrderBy(v => v.CreatedAt).ToListAsync();

    public async Task<Pack> CreatePackAsync(PackEdit edit)
    {
        if (string.IsNullOrWhiteSpace(edit.Name)) throw new StudioException("A pack needs a name.");
        var pack = new Pack();
        Apply(pack, edit);
        db.Packs.Add(pack);
        await db.SaveChangesAsync();
        await notifier.Changed<Pack>(pack.Id, pack.Id);
        return pack;
    }

    public async Task<Pack> UpdatePackAsync(Guid id, PackEdit edit)
    {
        var pack = await GetPackAsync(id);
        Apply(pack, edit);
        await db.SaveChangesAsync();
        await notifier.Changed<Pack>(pack.Id, pack.Id);
        return pack;
    }

    /// <summary>
    /// Deletes a pack and everything in it (assets, variants, concepts, masks, manifests, programs, builds, scenes,
    /// palette, jobs, chats), after cancelling its queued and running jobs. Knowledge notes and stored files stay.
    /// </summary>
    public async Task DeletePackAsync(Guid id)
    {
        await GetPackAsync(id);
        foreach (var jobId in await db.Jobs.Where(j => j.PackId == id && (j.State == JobState.Queued || j.State == JobState.Running))
                     .Select(j => j.Id).ToListAsync())
            await jobs.CancelAsync(jobId);
        await using var transaction = await db.Database.BeginTransactionAsync();
        var assets = db.Assets.Where(a => a.PackId == id).Select(a => a.Id);
        var concepts = db.ConceptImages.Where(c => c.PackId == id).Select(c => c.Id);
        var paletteVariants = db.PaletteVariants.Where(v => v.PackId == id).Select(v => v.Id);
        var packJobs = db.Jobs.Where(j => j.PackId == id).Select(j => j.Id);
        await db.PartMasks.Where(m => concepts.Contains(m.ConceptImageId)).ExecuteDeleteAsync();
        await db.ConceptImages.Where(c => c.PackId == id).ExecuteDeleteAsync();
        await db.Builds.Where(b => assets.Contains(b.AssetId)).ExecuteDeleteAsync();
        await db.ProgramVersions.Where(v => assets.Contains(v.AssetId)).ExecuteDeleteAsync();
        await db.Manifests.Where(m => assets.Contains(m.AssetId)).ExecuteDeleteAsync();
        await db.AssetVariants.Where(v => assets.Contains(v.AssetId)).ExecuteDeleteAsync();
        await db.Assets.Where(a => a.PackId == id).ExecuteDeleteAsync();
        await db.Scenes.Where(s => s.PackId == id).ExecuteDeleteAsync();
        await db.PaletteVariantColors.Where(c => paletteVariants.Contains(c.VariantId)).ExecuteDeleteAsync();
        await db.PaletteVariants.Where(v => v.PackId == id).ExecuteDeleteAsync();
        await db.PaletteEntries.Where(e => e.PackId == id).ExecuteDeleteAsync();
        await db.StyleReferences.Where(r => r.PackId == id).ExecuteDeleteAsync();
        await db.JobEvents.Where(e => packJobs.Contains(e.JobId)).ExecuteDeleteAsync();
        await db.Jobs.Where(j => j.PackId == id).ExecuteDeleteAsync();
        await db.Chats.Where(c => c.PackId == id).ExecuteDeleteAsync();
        await db.Packs.Where(p => p.Id == id).ExecuteDeleteAsync();
        await transaction.CommitAsync();
        db.ChangeTracker.Clear();
        await notifier.Changed<Pack>(id, id);
    }

    private static void Apply(Pack pack, PackEdit edit)
    {
        if (edit.Name is { } name) pack.Name = name.Trim();
        if (edit.Instructions is { } instructions) pack.Instructions = instructions;
        if (edit.StyleText is { } style) pack.StyleText = style;
        if (edit.PolyBudget is { } budget) pack.PolyBudget = budget > 0 ? budget : throw new StudioException("The polygon budget must be positive.");
        if (edit.ShadingMode is { } mode) pack.ShadingMode = Enum.IsDefined(mode) ? mode : throw new StudioException("The shading mode must be Flat or Smooth.");
        if (edit.HardEdgeAngle is { } angle) pack.HardEdgeAngle = angle is >= 0 and <= 180 ? angle : throw new StudioException("The hard-edge angle must be between 0 and 180 degrees.");
        if (edit.ShadeStrength is { } shade) pack.ShadeStrength = shade is >= 0 and <= 1 ? shade : throw new StudioException("The shade strength must be between 0 and 1.");
    }

    public async Task<StyleReference> AddStyleReferenceAsync(Guid packId, Stream content, string name, string? contentType)
    {
        await GetPackAsync(packId);
        var file = await files.AddAsync(content, name, contentType);
        var reference = new StyleReference { PackId = packId, FileId = file.Id, Label = Path.GetFileNameWithoutExtension(name) };
        db.StyleReferences.Add(reference);
        await db.SaveChangesAsync();
        await notifier.Changed<StyleReference>(reference.Id, packId);
        return reference;
    }

    public async Task RemoveStyleReferenceAsync(Guid id)
    {
        var reference = await db.StyleReferences.FindAsync(id) ?? throw StudioException.NotFound("Style reference");
        db.StyleReferences.Remove(reference);
        await db.SaveChangesAsync();
        await notifier.Changed<StyleReference>(id, reference.PackId);
    }

    /// <summary>Creates an asset with its "default" variant.</summary>
    public async Task<Asset> CreateAssetAsync(Guid packId, string name, string description, int? polyBudget = null)
    {
        await GetPackAsync(packId);
        if (string.IsNullOrWhiteSpace(name)) throw new StudioException("An asset needs a name.");
        var asset = new Asset { PackId = packId, Name = name.Trim(), Description = description, PolyBudget = Budget(polyBudget) };
        var variant = new AssetVariant { AssetId = asset.Id, Name = DefaultVariantName };
        asset.DefaultVariantId = variant.Id;
        db.Assets.Add(asset);
        db.AssetVariants.Add(variant);
        await db.SaveChangesAsync();
        await notifier.Changed<Asset>(asset.Id, packId, asset.Id);
        return asset;
    }

    public async Task<Asset> UpdateAssetAsync(Guid id, AssetEdit edit)
    {
        var asset = await GetAssetAsync(id);
        if (edit.Name is { } name) asset.Name = string.IsNullOrWhiteSpace(name) ? throw new StudioException("An asset needs a name.") : name.Trim();
        if (edit.Description is { } description) asset.Description = description;
        if (edit.PolyBudget is { } budget) asset.PolyBudget = Budget(budget);
        await db.SaveChangesAsync();
        await notifier.Changed<Asset>(asset.Id, asset.PackId, asset.Id);
        return asset;
    }

    /// <summary>A budget of 0 (or none) means "use the pack's budget".</summary>
    private static int? Budget(int? budget) => budget switch
    {
        null or 0 => null,
        < 0 => throw new StudioException("The triangle budget must be positive."),
        _ => budget,
    };

    /// <summary>Deletes an asset with its variants, concepts, masks, manifests, programs and builds. Refused while a scene places it.</summary>
    public async Task DeleteAssetAsync(Guid id)
    {
        var asset = await GetAssetAsync(id);
        var scenes = await ScenesUsingAsync(asset.PackId, p => p.AssetId == id);
        if (scenes.Count > 0)
            throw new StudioException($"\"{asset.Name}\" is placed in {string.Join(", ", scenes)}; remove it from the scene first.", StatusCodes.Status409Conflict);
        var concepts = db.ConceptImages.Where(c => c.AssetId == id).Select(c => c.Id);
        await db.PartMasks.Where(m => concepts.Contains(m.ConceptImageId)).ExecuteDeleteAsync();
        await db.ConceptImages.Where(c => c.AssetId == id).ExecuteDeleteAsync();
        await db.Manifests.Where(m => m.AssetId == id).ExecuteDeleteAsync();
        await db.Builds.Where(b => b.AssetId == id).ExecuteDeleteAsync();
        await db.ProgramVersions.Where(v => v.AssetId == id).ExecuteDeleteAsync();
        await db.AssetVariants.Where(v => v.AssetId == id).ExecuteDeleteAsync();
        db.Assets.Remove(asset);
        await db.SaveChangesAsync();
        await notifier.Changed<Asset>(id, asset.PackId, id);
    }

    /// <summary>Names of the pack's scenes with a placement matching the filter.</summary>
    private async Task<List<string>> ScenesUsingAsync(Guid packId, Func<ScenePlacement, bool> uses) =>
        (await db.Scenes.Where(s => s.PackId == packId).ToListAsync())
        .Where(s => s.Placements.Any(uses)).Select(s => s.Name).ToList();

    /// <summary>
    /// A new variant of an asset: empty, from another variant (its manifest, and its current program as version 1,
    /// which the caller builds), or from a hero of the asset (moved to the variant with its views, and picked).
    /// </summary>
    public async Task<(AssetVariant Variant, ProgramVersion? Copied)> CreateVariantAsync(Guid assetId, VariantCreate create)
    {
        var asset = await GetAssetAsync(assetId);
        var variant = new AssetVariant { AssetId = assetId, Name = await UniqueNameAsync(assetId, create.Name) };
        db.AssetVariants.Add(variant);
        ProgramVersion? copied = null;
        if (create.FromVariantId is { } fromId)
        {
            var source = await VariantOfAsync(assetId, fromId);
            if (await db.Manifests.FindAsync(source.Id) is { } manifest)
            {
                db.Manifests.Add(new Manifest { VariantId = variant.Id, AssetId = assetId, Content = manifest.Content.DeepClone().AsObject() });
                variant.Status = AssetStatus.Manifest;
            }
            if (source.CurrentProgramVersionId is { } currentId && await db.ProgramVersions.FindAsync(currentId) is { } current)
            {
                copied = new ProgramVersion
                {
                    AssetId = assetId, VariantId = variant.Id, Number = 1, Source = current.Source,
                    Note = $"copied from {source.Name} v{current.Number}",
                };
                db.ProgramVersions.Add(copied);
                variant.CurrentProgramVersionId = copied.Id;
                variant.Status = AssetStatus.Manifest;
            }
        }
        else if (create.FromHeroId is { } heroId)
        {
            await MoveHeroAsync(asset, heroId, variant);
        }
        await db.SaveChangesAsync();
        await SyncAssetStatusAsync(asset);
        await notifier.Changed<AssetVariant>(variant.Id, asset.PackId, assetId);
        return (variant, copied);
    }

    /// <summary>Moves a hero and its views to a variant and makes it the variant's picked reference (not saved).</summary>
    private async Task MoveHeroAsync(Asset asset, Guid heroId, AssetVariant variant)
    {
        var hero = await db.ConceptImages.FindAsync(heroId);
        if (hero is null || hero.Kind != ConceptKind.Hero || hero.AssetId != asset.Id)
            throw new StudioException("A variant can start only from a hero image of the same asset.");
        if (hero.Selection == Selection.Rejected) throw new StudioException("This hero was rejected; it can't become a variant's reference.");
        hero.VariantId = variant.Id;
        hero.Selection = Selection.Picked;
        await db.ConceptImages.Where(c => c.SourceConceptId == heroId && c.Kind == ConceptKind.View)
            .ExecuteUpdateAsync(u => u.SetProperty(c => c.VariantId, variant.Id));
    }

    private async Task<string> UniqueNameAsync(Guid assetId, string? name, Guid? except = null)
    {
        var trimmed = string.IsNullOrWhiteSpace(name) ? throw new StudioException("A variant needs a name.") : name.Trim();
        if (await db.AssetVariants.AnyAsync(v => v.AssetId == assetId && v.Name == trimmed && v.Id != except))
            throw new StudioException($"The asset already has a variant \"{trimmed}\".", StatusCodes.Status409Conflict);
        return trimmed;
    }

    public async Task<AssetVariant> UpdateVariantAsync(Guid id, VariantUpdate update)
    {
        var variant = await GetVariantAsync(id);
        var asset = await GetAssetAsync(variant.AssetId);
        if (update.Name is { } name) variant.Name = await UniqueNameAsync(asset.Id, name, id);
        if (update.MakeDefault == true) asset.DefaultVariantId = id;
        await db.SaveChangesAsync();
        await notifier.Changed<AssetVariant>(id, asset.PackId, asset.Id);
        return variant;
    }

    /// <summary>Deletes a variant with its heroes, views, masks, manifest, programs and builds. Refused for the only
    /// variant and while a scene uses it (placements without a variant use the default one).</summary>
    public async Task DeleteVariantAsync(Guid id)
    {
        var variant = await GetVariantAsync(id);
        var asset = await GetAssetAsync(variant.AssetId);
        var others = await db.AssetVariants.Where(v => v.AssetId == asset.Id && v.Id != id).OrderBy(v => v.CreatedAt).ToListAsync();
        if (others.Count == 0) throw new StudioException("An asset keeps at least one variant; delete the asset instead.", StatusCodes.Status409Conflict);
        var isDefault = asset.DefaultVariantId == id;
        var scenes = (await db.Scenes.Where(s => s.PackId == asset.PackId).ToListAsync())
            .Where(s => s.Placements.Any(p => p.AssetId == asset.Id && (p.VariantId == id || (p.VariantId is null && isDefault)))
                        || s.Versions.Any(v => v.VariantId == id))
            .Select(s => s.Name).ToList();
        if (scenes.Count > 0)
            throw new StudioException($"The variant \"{variant.Name}\" is used in {string.Join(", ", scenes)}; change those scenes first.", StatusCodes.Status409Conflict);
        var concepts = db.ConceptImages.Where(c => c.VariantId == id).Select(c => c.Id);
        await db.PartMasks.Where(m => concepts.Contains(m.ConceptImageId)).ExecuteDeleteAsync();
        await db.ConceptImages.Where(c => c.VariantId == id).ExecuteDeleteAsync();
        await db.Manifests.Where(m => m.VariantId == id).ExecuteDeleteAsync();
        await db.Builds.Where(b => b.VariantId == id).ExecuteDeleteAsync();
        await db.ProgramVersions.Where(v => v.VariantId == id).ExecuteDeleteAsync();
        if (isDefault) asset.DefaultVariantId = others[0].Id;
        db.AssetVariants.Remove(variant);
        await db.SaveChangesAsync();
        await SyncAssetStatusAsync(asset);
        await notifier.Changed<AssetVariant>(id, asset.PackId, asset.Id);
    }

    /// <summary>Sets the asset's status to the furthest status of its variants and saves.</summary>
    public async Task SyncAssetStatusAsync(Asset asset)
    {
        var statuses = await db.AssetVariants.Where(v => v.AssetId == asset.Id).Select(v => v.Status).ToListAsync();
        asset.Status = statuses.Count == 0 ? AssetStatus.Concept : statuses.Max();
        await db.SaveChangesAsync();
    }

    /// <summary>Deletes a concept image and its part masks (the files stay: builds keep their own inputs).</summary>
    public async Task DeleteConceptAsync(Guid id)
    {
        var concept = await db.ConceptImages.FindAsync(id) ?? throw StudioException.NotFound("Concept image");
        // A hero takes its views (and their masks) with it.
        var gone = db.ConceptImages.Where(c => c.Id == id || (c.SourceConceptId == id && c.Kind == ConceptKind.View));
        await db.PartMasks.Where(m => gone.Any(c => c.Id == m.ConceptImageId)).ExecuteDeleteAsync();
        await gone.ExecuteDeleteAsync();
        await notifier.Changed<ConceptImage>(id, concept.PackId, concept.AssetId);
    }

    /// <summary>
    /// Picks, rejects or clears a concept. A variant has at most one picked hero: picking another one needs
    /// <see cref="SelectionEdit.OnConflict"/> ("replace" unpicks the old reference, keeping its views; "newVariant"
    /// starts a variant named <see cref="SelectionEdit.VariantName"/> from the hero), and is refused without it.
    /// </summary>
    public async Task<ConceptImage> SelectConceptAsync(Guid id, SelectionEdit edit)
    {
        var concept = await db.ConceptImages.FindAsync(id) ?? throw StudioException.NotFound("Concept image");
        if (edit.Selection == Selection.Picked && concept.Kind == ConceptKind.Hero && concept.VariantId is { } variantId
            && concept.Selection != Selection.Picked)
        {
            var reference = await db.ConceptImages.FirstOrDefaultAsync(c => c.VariantId == variantId && c.Kind == ConceptKind.Hero
                                                                            && c.Selection == Selection.Picked && c.Id != id);
            if (reference is not null)
            {
                switch (edit.OnConflict)
                {
                    case SelectionConflicts.Replace:
                        reference.Selection = Selection.None;
                        break;
                    case SelectionConflicts.NewVariant:
                        await CreateVariantAsync(concept.AssetId!.Value, new VariantCreate(edit.VariantName ?? "", FromHeroId: id));
                        return concept;
                    default:
                        var name = (await db.AssetVariants.FindAsync(variantId))?.Name;
                        throw new StudioException($"The variant \"{name}\" already has a reference hero. Choose \"replace\" to make this hero " +
                                                  "the reference, or \"newVariant\" with a name to start a new variant from it.",
                            StatusCodes.Status409Conflict, SelectionConflicts.ReferenceExists);
                }
            }
        }
        concept.Selection = edit.Selection;
        await db.SaveChangesAsync();
        await notifier.Changed<ConceptImage>(id, concept.PackId, concept.AssetId);
        return concept;
    }

    /// <summary>Concepts of a pack (or of one asset). Rejected ones, and the views of rejected heroes, are excluded
    /// unless asked for.</summary>
    public Task<List<ConceptImage>> ListConceptsAsync(Guid packId, Guid? assetId = null, bool includeRejected = false) =>
        db.ConceptImages
            .Where(c => c.PackId == packId && (assetId == null || c.AssetId == assetId)
                        && (includeRejected || (c.Selection != Selection.Rejected
                            && !db.ConceptImages.Any(h => h.Id == c.SourceConceptId && h.Selection == Selection.Rejected))))
            .OrderBy(c => c.CreatedAt).ToListAsync();

    public async Task<Manifest> SaveManifestAsync(Guid assetId, Guid? variantId, JsonObject content)
    {
        var asset = await GetAssetAsync(assetId);
        var variant = await VariantOfAsync(assetId, variantId);
        ManifestRules.Validate(content);
        var manifest = await db.Manifests.FindAsync(variant.Id);
        if (manifest is null) db.Manifests.Add(manifest = new Manifest { VariantId = variant.Id, AssetId = assetId });
        manifest.Content = content;
        manifest.UpdatedAt = DateTimeOffset.UtcNow;
        if (variant.Status < AssetStatus.Manifest) variant.Status = AssetStatus.Manifest;
        await db.SaveChangesAsync();
        await SyncAssetStatusAsync(asset);
        await notifier.Changed<Manifest>(variant.Id, asset.PackId, assetId);
        return manifest;
    }

    /// <summary>Makes a version the current one of its variant.</summary>
    public async Task<AssetVariant> SetCurrentVersionAsync(Guid assetId, Guid versionId)
    {
        var asset = await GetAssetAsync(assetId);
        var version = await db.ProgramVersions.FirstOrDefaultAsync(v => v.Id == versionId && v.AssetId == assetId)
                      ?? throw StudioException.NotFound("Program version");
        var variant = await GetVariantAsync(version.VariantId);
        variant.CurrentProgramVersionId = versionId;
        var build = await db.Builds.Where(b => b.ProgramVersionId == versionId).OrderByDescending(b => b.CreatedAt).FirstOrDefaultAsync();
        variant.Status = build is null ? AssetStatus.Manifest : build.Validated ? AssetStatus.Validated : AssetStatus.Built;
        await db.SaveChangesAsync();
        await SyncAssetStatusAsync(asset);
        await notifier.Changed<AssetVariant>(variant.Id, asset.PackId, assetId);
        return variant;
    }
}

/// <summary>
/// Manifest shape: <c>{ "symmetry": ["x"], "parts": [ { "name", "parent"?, "primitive"?, "mirror"?,
/// "connections": [ { "to", "type": "fixed|rotate|slide", "axis"? } ] } ] }</c>.
/// </summary>
public static class ManifestRules
{
    private static readonly string[] ConnectionTypes = ["fixed", "rotate", "slide"];

    public static void Validate(JsonObject content)
    {
        if (content["parts"] is not JsonArray parts || parts.Count == 0)
            throw new StudioException("The manifest needs a non-empty \"parts\" array.");
        var names = new HashSet<string>();
        foreach (var part in parts)
        {
            var name = part?["name"]?.GetValue<string>();
            if (string.IsNullOrWhiteSpace(name)) throw new StudioException("Every part needs a \"name\".");
            if (!names.Add(name)) throw new StudioException($"Part \"{name}\" appears twice.");
        }
        var roots = 0;
        foreach (var part in parts)
        {
            var name = part!["name"]!.GetValue<string>();
            var parent = part["parent"]?.GetValue<string>();
            if (parent is null) roots++;
            else if (!names.Contains(parent)) throw new StudioException($"Part \"{name}\" references unknown parent \"{parent}\".");
            foreach (var connection in part["connections"]?.AsArray() ?? [])
            {
                var to = connection?["to"]?.GetValue<string>();
                if (to is null || !names.Contains(to)) throw new StudioException($"Part \"{name}\" connects to unknown part \"{to}\".");
                var type = connection!["type"]?.GetValue<string>() ?? "fixed";
                if (!ConnectionTypes.Contains(type)) throw new StudioException($"Connection type \"{type}\" of \"{name}\" is not one of fixed, rotate, slide.");
            }
        }
        if (roots != 1) throw new StudioException($"The manifest needs exactly one root part (without parent), found {roots}.");
    }
}
