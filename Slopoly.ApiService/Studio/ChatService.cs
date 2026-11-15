using System.Globalization;
using System.Text.Json.Nodes;
using Microsoft.EntityFrameworkCore;
using Slopoly.ApiService.Data;
using Slopoly.ApiService.Infrastructure;
using Slopoly.ApiService.Jobs;
using Slopoly.Contracts;

namespace Slopoly.ApiService.Studio;

/// <summary>
/// Chats with the agent. Each message is an agent-turn job whose prompt the API composes from the database: the first
/// message of a chat carries a [Context] block for the page the chat was started on, later ones a [Viewing: …] line
/// for the page the message is sent from. Names and states come from the database, so the agent never gets stale UI
/// text.
/// </summary>
public sealed class ChatService(SlopolyDb db, JobService jobs, Notifier notifier)
{
    public const int MaxTitle = 60;

    public async Task<Chat> GetAsync(Guid id) => await db.Chats.FindAsync(id) ?? throw StudioException.NotFound("Chat");

    public async Task<Chat> CreateAsync(ChatContext context)
    {
        if (context.PackId is { } packId && !await db.Packs.AnyAsync(p => p.Id == packId)) throw StudioException.NotFound("Pack");
        var chat = new Chat
        {
            PackId = context.PackId, Context = context, AssetId = context.AssetId, VariantId = context.VariantId, SceneId = context.SceneId,
            Title = "New chat",
        };
        db.Chats.Add(chat);
        await db.SaveChangesAsync();
        await notifier.Changed<Chat>(chat.Id, chat.PackId);
        return chat;
    }

    /// <summary>Chats, newest activity first, optionally of one pack, asset or scene.</summary>
    public async Task<Page<Chat>> ListAsync(Guid? packId, Guid? assetId, Guid? sceneId, int skip, int take)
    {
        var query = db.Chats.Where(c => (packId == null || c.PackId == packId) && (assetId == null || c.AssetId == assetId)
                                        && (sceneId == null || c.SceneId == sceneId));
        return new(await query.OrderByDescending(c => c.UpdatedAt).Skip(Math.Max(0, skip)).Take(Paging.Take(take)).ToListAsync(),
            await query.CountAsync());
    }

    /// <summary>A chat's turns, newest page first (before: a turn's job id, to load the turns before it); each page
    /// is in chronological order.</summary>
    public async Task<Page<ChatTurn>> TurnsAsync(Guid chatId, Guid? before, int take)
    {
        await GetAsync(chatId);
        var all = db.Jobs.Where(j => j.ChatId == chatId && j.Kind == JobKinds.AgentTurn);
        var query = all;
        if (before is { } id && await db.Jobs.FindAsync(id) is { } edge)
            query = query.Where(j => j.CreatedAt < edge.CreatedAt);
        var turns = (await query.OrderByDescending(j => j.CreatedAt).Take(Paging.Take(take, 20)).ToListAsync()).AsEnumerable().Reverse().ToList();
        var ids = turns.Select(t => t.Id).ToList();
        var events = (await db.JobEvents.Where(e => ids.Contains(e.JobId)).OrderBy(e => e.Id).ToListAsync()).ToLookup(e => e.JobId);
        return new(turns.Select(t => new ChatTurn(t, events[t.Id].ToList())).ToList(), await all.CountAsync());
    }

    public async Task<Job> SendAsync(Guid chatId, ChatMessage message)
    {
        var chat = await GetAsync(chatId);
        if (string.IsNullOrWhiteSpace(message.Message)) throw new StudioException("The message is empty.");
        var first = !await db.Jobs.AnyAsync(j => j.ChatId == chatId && j.Kind == JobKinds.AgentTurn);
        var text = message.Message.Trim();
        var prompt = first
            ? $"[Context]\n{string.Join("\n", await DescribeAsync(chat.Context, full: true))}\n[/Context]\n\n{text}"
            : $"[Viewing: {string.Join(" · ", await DescribeAsync(message.Context ?? chat.Context, full: false))}]\n{text}";
        if (first) chat.Title = text.Length <= MaxTitle ? text : text[..(MaxTitle - 1)].TrimEnd() + "…";
        chat.UpdatedAt = DateTimeOffset.UtcNow;
        await db.SaveChangesAsync();
        await notifier.Changed<Chat>(chat.Id, chat.PackId);
        return await jobs.SubmitAsync(JobKinds.AgentTurn, null, chat.PackId, null,
            new JsonObject { ["message"] = text, ["prompt"] = prompt, ["sessionId"] = chat.SessionId, ["chatId"] = chat.Id }, chat.Id);
    }

    /// <summary>Cancels the chat's queued and running turns.</summary>
    public async Task<List<Job>> StopAsync(Guid chatId)
    {
        await GetAsync(chatId);
        var active = await db.Jobs.Where(j => j.ChatId == chatId && (j.State == JobState.Queued || j.State == JobState.Running)).ToListAsync();
        foreach (var job in active) await jobs.CancelAsync(job.Id);
        return active;
    }

    /// <summary>One line per object of the page: name, id and key state. Short form (for the viewing line): names
    /// and ids only.</summary>
    public async Task<List<string>> DescribeAsync(ChatContext context, bool full)
    {
        var lines = new List<string> { $"The user is on the {context.Page} page{(context.Tab is { } tab ? $" ({tab} tab)" : "")}." };
        if (!full) lines[0] = $"{context.Page} page{(context.Tab is { } t ? $" ({t} tab)" : "")}";
        if (context.PackId is { } packId && await db.Packs.FindAsync(packId) is { } pack)
            lines.Add(full
                ? $"Pack \"{pack.Name}\" (id {pack.Id}): budget {pack.PolyBudget} triangles, shading {pack.ShadingMode}, hard-edge angle {Num(pack.HardEdgeAngle)}°, shade strength {Num(pack.ShadeStrength)}."
                : $"pack \"{pack.Name}\" ({pack.Id})");
        else if (full && context.Page != ChatPages.Knowledge) lines.Add("No pack.");
        if (context.AssetId is { } assetId && await db.Assets.FindAsync(assetId) is { } asset)
        {
            lines.Add(full
                ? $"Asset \"{asset.Name}\" (id {asset.Id}): {asset.Description}; status {asset.Status}; budget {(asset.PolyBudget is { } b ? $"{b} triangles" : "the pack's")}."
                : $"asset \"{asset.Name}\" ({asset.Id})");
            var variant = await db.AssetVariants.FindAsync(context.VariantId ?? asset.DefaultVariantId);
            if (variant is not null && variant.AssetId == asset.Id)
            {
                var current = variant.CurrentProgramVersionId is { } cv ? await db.ProgramVersions.FindAsync(cv) : null;
                var hero = await db.ConceptImages.FirstOrDefaultAsync(c => c.VariantId == variant.Id && c.Kind == ConceptKind.Hero && c.Selection == Selection.Picked);
                lines.Add(full
                    ? $"Variant \"{variant.Name}\" (id {variant.Id}{(variant.Id == asset.DefaultVariantId ? ", default" : "")}): status {variant.Status}; " +
                      $"current version {(current is null ? "none" : $"v{current.Number} (id {current.Id})")}; reference hero {(hero is null ? "none" : $"id {hero.Id}")}."
                    : $"variant \"{variant.Name}\" ({variant.Id})");
            }
        }
        if (context.BuildId is { } buildId && await db.Builds.FindAsync(buildId) is { } build)
        {
            var version = await db.ProgramVersions.FindAsync(build.ProgramVersionId);
            lines.Add(full
                ? $"Selected build (id {build.Id}): program v{version?.Number} (id {build.ProgramVersionId}), validated {(build.Validated ? "yes" : "no")}, " +
                  $"mean object IoU {build.Report?["silhouette"]?["mean_object_iou"]?.ToString() ?? "–"}."
                : $"build {build.Id} (v{version?.Number})");
        }
        if (context.SceneId is { } sceneId && await db.Scenes.FindAsync(sceneId) is { } scene)
        {
            if (!full) lines.Add($"scene \"{scene.Name}\" ({scene.Id})");
            else
            {
                lines.Add($"Scene \"{scene.Name}\" (id {scene.Id}): {scene.Placements.Count} placements.");
                var assetIds = scene.Placements.Select(p => p.AssetId).Distinct().ToList();
                var assets = await db.Assets.Where(a => assetIds.Contains(a.Id)).ToDictionaryAsync(a => a.Id);
                var variants = await db.AssetVariants.Where(v => assetIds.Contains(v.AssetId)).ToDictionaryAsync(v => v.Id);
                foreach (var p in scene.Placements)
                {
                    if (!assets.TryGetValue(p.AssetId, out var a)) continue;
                    var v = variants.GetValueOrDefault(p.VariantId ?? a.DefaultVariantId);
                    var chosen = scene.Versions.FirstOrDefault(x => x.AssetId == a.Id && x.VariantId == v?.Id)?.ProgramVersionId;
                    var number = chosen is { } id ? (await db.ProgramVersions.FindAsync(id))?.Number : null;
                    lines.Add($"- \"{p.Name}\": asset \"{a.Name}\" (id {a.Id}), variant \"{v?.Name}\" (id {v?.Id}), version {(number is { } n ? $"v{n}" : "current")}, at [{string.Join(", ", p.At.Select(Num))}].");
                }
            }
        }
        if (context.ConceptId is { } conceptId && await db.ConceptImages.FindAsync(conceptId) is { } concept)
            lines.Add(full
                ? $"Concept image (id {concept.Id}): {concept.Kind}{(concept.View is { } view ? $" ({view})" : "")}, {concept.Selection}" +
                  $"{(concept.SourceConceptId is { } source ? $", view of hero {source}" : "")}{(concept.VariantId is { } vid ? $", variant {vid}" : "")}."
                : $"concept {concept.Id} ({concept.Kind})");
        return lines;
    }

    private static string Num(double value) => value.ToString("0.##", CultureInfo.InvariantCulture);
}

/// <summary>Page sizes of history lists.</summary>
public static class Paging
{
    public const int Max = 200;
    public static int Take(int take, int fallback = 25) => take <= 0 ? fallback : Math.Min(take, Max);

    public static async Task<Page<T>> PageAsync<T>(this IQueryable<T> ordered, int skip, int take) =>
        new(await ordered.Skip(Math.Max(0, skip)).Take(Take(take)).ToListAsync(), await ordered.CountAsync());
}
