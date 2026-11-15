using System.Collections.Concurrent;
using System.Text.Json;
using System.Text.Json.Nodes;
using System.Text.RegularExpressions;
using Microsoft.EntityFrameworkCore;
using Slopoly.ApiService.Data;
using Slopoly.ApiService.Infrastructure;
using Slopoly.ApiService.Jobs;
using Slopoly.Contracts;

namespace Slopoly.ApiService.Studio;

/// <summary>Main palette and variants (design §13). Slots are assigned once; colours change freely.</summary>
public sealed partial class PaletteService(SlopolyDb db, Notifier notifier, PaletteRenderScheduler render)
{
    public const int MaxSolids = 256, MaxGradients = 32;

    public async Task<List<PaletteSlot>> MainEntriesAsync(Guid packId) =>
        (await db.PaletteEntries.Where(e => e.PackId == packId).ToListAsync())
        .OrderBy(e => e.Kind).ThenBy(e => e.Slot)
        .Select(e => new PaletteSlot(e.Id, e.Role, e.Kind, e.Slot, e.Color, e.Color2)).ToList();

    public async Task<PaletteView> GetAsync(Guid packId)
    {
        var pack = await db.Packs.FindAsync(packId) ?? throw StudioException.NotFound("Pack");
        var entries = await db.PaletteEntries.Where(e => e.PackId == packId).ToListAsync();
        var variants = await db.PaletteVariants.Where(v => v.PackId == packId).OrderBy(v => v.Name).ToListAsync();
        var views = new List<VariantView>();
        foreach (var variant in variants) views.Add(new(variant.Id, variant.Name, variant.TextureFileId, await ResolveAsync(variant, entries)));
        return new(entries.OrderBy(e => e.Kind).ThenBy(e => e.Slot).ToList(), views, pack.PaletteTextureFileId);
    }

    /// <summary>Adds entries or updates existing ones (matched by role) of the main palette.</summary>
    public async Task<List<PaletteEntry>> UpsertEntriesAsync(Guid packId, IReadOnlyList<PaletteEntryEdit> edits)
    {
        _ = await db.Packs.FindAsync(packId) ?? throw StudioException.NotFound("Pack");
        var entries = await db.PaletteEntries.Where(e => e.PackId == packId).ToListAsync();
        var changed = new List<PaletteEntry>();
        foreach (var edit in edits)
        {
            var role = edit.Role?.Trim() ?? "";
            if (role.Length == 0) throw new StudioException("Palette entries need a role name.");
            var entry = entries.FirstOrDefault(e => e.Role.Equals(role, StringComparison.OrdinalIgnoreCase));
            if (entry is null)
            {
                var kind = edit.Kind ?? (edit.Color2 is null ? PaletteKind.Solid : PaletteKind.Gradient);
                entry = new PaletteEntry { PackId = packId, Role = role, Kind = kind, Slot = FreeSlot(entries, kind) };
                entries.Add(entry);
                db.PaletteEntries.Add(entry);
            }
            else if (edit.Kind is { } kind && kind != entry.Kind)
                throw new StudioException($"\"{role}\" is a {entry.Kind.ToString().ToLowerInvariant()} entry; its kind can't change because builds point at its slot.");
            entry.Color = Hex(edit.Color ?? entry.Color);
            entry.Color2 = entry.Kind == PaletteKind.Gradient
                ? Hex(edit.Color2 ?? entry.Color2 ?? throw new StudioException($"Gradient \"{role}\" needs an end colour (color2)."))
                : null;
            changed.Add(entry);
        }
        await SaveAndRenderAsync(packId);
        return changed;
    }

    /// <summary>Adds a new entry; fails when the role already exists (the UI's "add" action).</summary>
    public async Task<PaletteEntry> AddEntryAsync(Guid packId, PaletteEntryEdit edit)
    {
        if (await db.PaletteEntries.AnyAsync(e => e.PackId == packId && e.Role.ToLower() == edit.Role.Trim().ToLower()))
            throw new StudioException($"The pack already has a palette entry \"{edit.Role.Trim()}\".", StatusCodes.Status409Conflict);
        return (await UpsertEntriesAsync(packId, [edit]))[0];
    }

    public async Task DeleteEntryAsync(Guid entryId)
    {
        var entry = await db.PaletteEntries.FindAsync(entryId) ?? throw StudioException.NotFound("Palette entry");
        var users = await UsedByAsync(entryId);
        if (users.Count > 0)
            throw new StudioException($"\"{entry.Role}\" is used by {string.Join(", ", users)} and can't be deleted.", StatusCodes.Status409Conflict);
        db.PaletteEntries.Remove(entry);
        await db.PaletteVariantColors.Where(c => c.EntryId == entryId).ExecuteDeleteAsync();
        await SaveAndRenderAsync(entry.PackId);
    }

    /// <summary>Names of assets whose builds sample the entry.</summary>
    public async Task<List<string>> UsedByAsync(Guid entryId) =>
        await (from b in db.Builds
               where b.PaletteEntryIds.Contains(entryId)
               join a in db.Assets on b.AssetId equals a.Id
               select a.Name).Distinct().OrderBy(n => n).ToListAsync();

    /// <summary>Creates or updates a variant; roles not given keep their current (or the main) colour.</summary>
    public async Task<VariantView> UpsertVariantAsync(Guid packId, string name, IReadOnlyList<VariantColorEdit> colors)
    {
        name = name?.Trim() ?? "";
        if (name.Length == 0) throw new StudioException("A palette variant needs a name.");
        var entries = await db.PaletteEntries.Where(e => e.PackId == packId).ToListAsync();
        var variant = await db.PaletteVariants.FirstOrDefaultAsync(v => v.PackId == packId && v.Name == name);
        if (variant is null) db.PaletteVariants.Add(variant = new PaletteVariant { PackId = packId, Name = name });
        foreach (var color in colors)
        {
            var entry = entries.FirstOrDefault(e => e.Role.Equals(color.Role.Trim(), StringComparison.OrdinalIgnoreCase))
                ?? throw new StudioException($"The main palette has no entry \"{color.Role}\"; variants use the main palette's roles.");
            var row = await db.PaletteVariantColors.FindAsync(variant.Id, entry.Id);
            if (row is null) db.PaletteVariantColors.Add(row = new PaletteVariantColor { VariantId = variant.Id, EntryId = entry.Id });
            row.Color = Hex(color.Color);
            row.Color2 = entry.Kind == PaletteKind.Gradient ? Hex(color.Color2 ?? entry.Color2!) : null;
        }
        await SaveAndRenderAsync(packId);
        return new(variant.Id, variant.Name, variant.TextureFileId, await ResolveAsync(variant, entries));
    }

    public async Task DeleteVariantAsync(Guid variantId)
    {
        var variant = await db.PaletteVariants.FindAsync(variantId) ?? throw StudioException.NotFound("Palette variant");
        await db.PaletteVariantColors.Where(c => c.VariantId == variantId).ExecuteDeleteAsync();
        db.PaletteVariants.Remove(variant);
        await db.SaveChangesAsync();
        await notifier.Changed<PaletteVariant>(variantId, variant.PackId);
    }

    /// <summary>Variant colours with the main palette as fallback for roles the variant doesn't set.</summary>
    private async Task<List<PaletteSlot>> ResolveAsync(PaletteVariant variant, List<PaletteEntry> entries)
    {
        var own = await db.PaletteVariantColors.Where(c => c.VariantId == variant.Id).ToDictionaryAsync(c => c.EntryId);
        return entries.OrderBy(e => e.Kind).ThenBy(e => e.Slot).Select(e => own.TryGetValue(e.Id, out var c)
            ? new PaletteSlot(e.Id, e.Role, e.Kind, e.Slot, c.Color, c.Color2)
            : new PaletteSlot(e.Id, e.Role, e.Kind, e.Slot, e.Color, e.Color2)).ToList();
    }

    /// <summary>Inputs of a palette-render job: all textures plus the pack's current builds to refresh.</summary>
    public async Task<JsonObject> RenderInputsAsync(Guid packId)
    {
        var view = await GetAsync(packId);
        var builds = await (from v in db.AssetVariants
                            join a in db.Assets on v.AssetId equals a.Id
                            where a.PackId == packId && v.CurrentProgramVersionId != null
                            select db.Builds.Where(b => b.ProgramVersionId == v.CurrentProgramVersionId && b.GlbFileId != null)
                                .OrderByDescending(b => b.CreatedAt).FirstOrDefault())
            .Where(b => b != null).Select(b => new { buildId = b!.Id, glbFileId = b.GlbFileId }).ToListAsync();
        return new JsonObject
        {
            ["main"] = JsonSerializer.SerializeToNode(await MainEntriesAsync(packId), Broker.Json),
            ["variants"] = JsonSerializer.SerializeToNode(view.Variants.Select(v => new { v.Id, v.Name, v.Entries }), Broker.Json),
            ["builds"] = JsonSerializer.SerializeToNode(builds, Broker.Json),
        };
    }

    private async Task SaveAndRenderAsync(Guid packId)
    {
        await db.SaveChangesAsync();
        await notifier.Changed<PaletteEntry>(packId, packId);
        render.Schedule(packId);
    }

    private static int FreeSlot(List<PaletteEntry> entries, PaletteKind kind)
    {
        var used = entries.Where(e => e.Kind == kind).Select(e => e.Slot).ToHashSet();
        var max = kind == PaletteKind.Solid ? MaxSolids : MaxGradients;
        for (var slot = 0; slot < max; slot++) if (!used.Contains(slot)) return slot;
        throw new StudioException($"The palette has no free {kind.ToString().ToLowerInvariant()} slot (max {max}).");
    }

    private static string Hex(string color)
    {
        color = color.Trim();
        if (!color.StartsWith('#')) color = "#" + color;
        return HexColor().IsMatch(color) ? color.ToLowerInvariant() : throw new StudioException($"\"{color}\" is not a #rrggbb colour.");
    }

    [GeneratedRegex("^#[0-9a-fA-F]{6}$")]
    private static partial Regex HexColor();
}

/// <summary>Debounces palette edits into one palette-render job per pack (about 1 s after the last edit).</summary>
public sealed class PaletteRenderScheduler(IServiceScopeFactory scopes, ILogger<PaletteRenderScheduler> logger)
{
    public static TimeSpan Delay { get; set; } = TimeSpan.FromSeconds(1);
    private readonly ConcurrentDictionary<Guid, CancellationTokenSource> _pending = new();

    public void Schedule(Guid packId)
    {
        var cts = new CancellationTokenSource();
        if (_pending.TryGetValue(packId, out var previous)) previous.Cancel();
        _pending[packId] = cts;
        _ = RunAsync(packId, cts);
    }

    private async Task RunAsync(Guid packId, CancellationTokenSource cts)
    {
        try
        {
            await Task.Delay(Delay, cts.Token);
            _pending.TryRemove(new KeyValuePair<Guid, CancellationTokenSource>(packId, cts));
            await using var scope = scopes.CreateAsyncScope();
            var palette = scope.ServiceProvider.GetRequiredService<PaletteService>();
            await scope.ServiceProvider.GetRequiredService<JobService>()
                .SubmitAsync(JobKinds.PaletteRender, null, packId, null, await palette.RenderInputsAsync(packId));
        }
        catch (OperationCanceledException) { }
        catch (Exception ex) { logger.LogError(ex, "Palette render of pack {PackId} could not be queued", packId); }
    }
}

/// <summary>palette-render: <c>{ textureFileId, variants: { variantId: fileId }, builds: { buildId: glbFileId } }</c>.</summary>
public sealed class PaletteRenderResults(SlopolyDb db) : IJobResultHandler
{
    public bool Handles(Job job) => job.Kind == JobKinds.PaletteRender;

    public async Task ApplyAsync(Job job, JsonObject outputs)
    {
        if (await db.Packs.FindAsync(job.PackId) is { } pack) pack.PaletteTextureFileId = outputs["textureFileId"]?.GetValue<Guid>();
        foreach (var (id, file) in outputs["variants"]?.AsObject() ?? [])
            if (await db.PaletteVariants.FindAsync(Guid.Parse(id)) is { } variant) variant.TextureFileId = file!.GetValue<Guid>();
        foreach (var (id, file) in outputs["builds"]?.AsObject() ?? [])
            if (await db.Builds.FindAsync(Guid.Parse(id)) is { } build) build.GlbFileId = file!.GetValue<Guid>();
    }
}
