using System.Text.Json.Nodes;
using Microsoft.EntityFrameworkCore;
using Slopoly.ApiService.Data;
using Slopoly.ApiService.Infrastructure;
using Slopoly.Contracts;

namespace Slopoly.ApiService.Studio;

/// <summary>A request the API refuses; mapped to 400/404/409 for REST and to a tool error for MCP.</summary>
public sealed class StudioException(string message, int status = StatusCodes.Status400BadRequest) : Exception(message)
{
    public int Status { get; } = status;
    public static StudioException NotFound(string what) => new($"{what} not found.", StatusCodes.Status404NotFound);
}

/// <summary>Pack, asset, concept and program operations shared by the REST endpoints and the MCP tools.</summary>
public sealed class StudioService(SlopolyDb db, FileStore files, Notifier notifier)
{
    public async Task<Pack> GetPackAsync(Guid id) => await db.Packs.FindAsync(id) ?? throw StudioException.NotFound("Pack");

    public async Task<Asset> GetAssetAsync(Guid id) => await db.Assets.FindAsync(id) ?? throw StudioException.NotFound("Asset");

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

    private static void Apply(Pack pack, PackEdit edit)
    {
        if (edit.Name is { } name) pack.Name = name.Trim();
        if (edit.Instructions is { } instructions) pack.Instructions = instructions;
        if (edit.StyleText is { } style) pack.StyleText = style;
        if (edit.PolyBudget is { } budget) pack.PolyBudget = budget > 0 ? budget : throw new StudioException("The polygon budget must be positive.");
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

    public async Task<Asset> CreateAssetAsync(Guid packId, string name, string description)
    {
        await GetPackAsync(packId);
        if (string.IsNullOrWhiteSpace(name)) throw new StudioException("An asset needs a name.");
        var asset = new Asset { PackId = packId, Name = name.Trim(), Description = description };
        db.Assets.Add(asset);
        await db.SaveChangesAsync();
        await notifier.Changed<Asset>(asset.Id, packId, asset.Id);
        return asset;
    }

    public async Task<ConceptImage> SelectConceptAsync(Guid id, Selection selection)
    {
        var concept = await db.ConceptImages.FindAsync(id) ?? throw StudioException.NotFound("Concept image");
        concept.Selection = selection;
        await db.SaveChangesAsync();
        await notifier.Changed<ConceptImage>(id, concept.PackId, concept.AssetId);
        return concept;
    }

    /// <summary>Concepts of a pack (or of one asset), rejected ones excluded unless asked for.</summary>
    public Task<List<ConceptImage>> ListConceptsAsync(Guid packId, Guid? assetId = null, bool includeRejected = false) =>
        db.ConceptImages
            .Where(c => c.PackId == packId && (assetId == null || c.AssetId == assetId)
                        && (includeRejected || c.Selection != Selection.Rejected))
            .OrderBy(c => c.CreatedAt).ToListAsync();

    public async Task<Manifest> SaveManifestAsync(Guid assetId, JsonObject content)
    {
        var asset = await GetAssetAsync(assetId);
        ManifestRules.Validate(content);
        var manifest = await db.Manifests.FindAsync(assetId);
        if (manifest is null) db.Manifests.Add(manifest = new Manifest { AssetId = assetId });
        manifest.Content = content;
        manifest.UpdatedAt = DateTimeOffset.UtcNow;
        if (asset.Status < AssetStatus.Manifest) asset.Status = AssetStatus.Manifest;
        await db.SaveChangesAsync();
        await notifier.Changed<Manifest>(assetId, asset.PackId, assetId);
        return manifest;
    }

    public async Task<Asset> SetCurrentVersionAsync(Guid assetId, Guid versionId)
    {
        var asset = await GetAssetAsync(assetId);
        if (!await db.ProgramVersions.AnyAsync(v => v.Id == versionId && v.AssetId == assetId))
            throw StudioException.NotFound("Program version");
        asset.CurrentProgramVersionId = versionId;
        var build = await db.Builds.Where(b => b.ProgramVersionId == versionId).OrderByDescending(b => b.CreatedAt).FirstOrDefaultAsync();
        asset.Status = build is null ? AssetStatus.Manifest : build.Validated ? AssetStatus.Validated : AssetStatus.Built;
        await db.SaveChangesAsync();
        await notifier.Changed<Asset>(assetId, asset.PackId, assetId);
        return asset;
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
