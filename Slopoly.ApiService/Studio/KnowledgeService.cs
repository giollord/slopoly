using System.Text.RegularExpressions;
using Slopoly.ApiService.Infrastructure;
using Slopoly.Contracts;
using YamlDotNet.Serialization;
using YamlDotNet.Serialization.NamingConventions;

namespace Slopoly.ApiService.Studio;

/// <summary>
/// Global technique notes: <c>knowledge/&lt;slug&gt;.md</c> files with title, tags and summary front matter. They are few
/// and small, so search is a plain term score over the files, with no index.
/// </summary>
public sealed partial class KnowledgeService(SlopolyOptions options, Notifier notifier)
{
    private sealed class FrontMatter
    {
        public string Title { get; set; } = "";
        public List<string> Tags { get; set; } = [];
        public string Summary { get; set; } = "";
    }

    private static readonly IDeserializer Reader = new DeserializerBuilder()
        .WithNamingConvention(CamelCaseNamingConvention.Instance).IgnoreUnmatchedProperties().Build();
    private static readonly ISerializer Writer = new SerializerBuilder()
        .WithNamingConvention(CamelCaseNamingConvention.Instance).WithDefaultScalarStyle(YamlDotNet.Core.ScalarStyle.Any).Build();

    [GeneratedRegex("^[a-z0-9]+(-[a-z0-9]+)*$")]
    private static partial Regex SlugPattern();

    [GeneratedRegex(@"\A---\r?\n(.*?)\r?\n---\r?\n?(.*)\z", RegexOptions.Singleline)]
    private static partial Regex Document();

    [GeneratedRegex(@"[\p{L}\p{N}]+")]
    private static partial Regex Words();

    private string Folder => Path.GetFullPath(options.KnowledgeDir ?? Path.Combine(options.DataDir, "knowledge"));

    private string PathOf(string slug) =>
        SlugPattern().IsMatch(slug ?? "") ? Path.Combine(Folder, slug + ".md")
            : throw new StudioException($"\"{slug}\" is not a note name: use lowercase words joined by hyphens, e.g. \"hollow-containers\".");

    public async Task<List<KnowledgeNote>> ListAsync()
    {
        if (!Directory.Exists(Folder)) return [];
        var notes = new List<KnowledgeNote>();
        foreach (var file in Directory.EnumerateFiles(Folder, "*.md").Order())
        {
            var slug = Path.GetFileNameWithoutExtension(file);
            if (SlugPattern().IsMatch(slug)) notes.Add(Parse(slug, await File.ReadAllTextAsync(file)));
        }
        return notes;
    }

    public async Task<KnowledgeNote> ReadAsync(string slug)
    {
        var path = PathOf(slug);
        return File.Exists(path) ? Parse(slug, await File.ReadAllTextAsync(path)) : throw StudioException.NotFound($"Note \"{slug}\"");
    }

    /// <summary>
    /// Notes ranked by how often the query's words occur: title and tags count most, then summary, then body.
    /// An empty query returns every note.
    /// </summary>
    public async Task<List<KnowledgeHit>> SearchAsync(string query, int take = 8)
    {
        var terms = Words().Matches(query.ToLowerInvariant()).Select(m => m.Value).Where(t => t.Length > 1).Distinct().ToList();
        return (await ListAsync())
            .Select(n => (Note: n, Score: terms.Sum(t =>
                5 * Count(n.Title, t) + 5 * n.Tags.Sum(tag => Count(tag, t)) + 3 * Count(n.Summary, t) + Math.Min(Count(n.Body, t), 5))))
            .Where(x => terms.Count == 0 || x.Score > 0)
            .OrderByDescending(x => x.Score).ThenBy(x => x.Note.Slug).Take(take)
            .Select(x => new KnowledgeHit(x.Note.Slug, x.Note.Title, x.Note.Tags, x.Note.Summary, x.Score)).ToList();

        // Prefix match, so "crack" also finds "cracks" and "cracked".
        static int Count(string text, string term) => Words().Matches(text.ToLowerInvariant()).Count(w => w.Value.StartsWith(term, StringComparison.Ordinal));
    }

    public async Task<KnowledgeNote> WriteAsync(KnowledgeNote note)
    {
        var path = PathOf(note.Slug);
        if (string.IsNullOrWhiteSpace(note.Title)) throw new StudioException("A note needs a title.");
        if (string.IsNullOrWhiteSpace(note.Body)) throw new StudioException("A note needs a body.");
        var front = new FrontMatter
        {
            Title = note.Title.Trim(),
            Tags = note.Tags.Select(t => t.Trim().ToLowerInvariant()).Where(t => t.Length > 0).Distinct().ToList(),
            Summary = note.Summary.Trim(),
        };
        Directory.CreateDirectory(Folder);
        await File.WriteAllTextAsync(path, $"---\n{Writer.Serialize(front).TrimEnd()}\n---\n\n{note.Body.Trim().ReplaceLineEndings("\n")}\n");
        await notifier.Changed(nameof(KnowledgeNote), Guid.Empty);
        return await ReadAsync(note.Slug);
    }

    public async Task DeleteAsync(string slug)
    {
        var path = PathOf(slug);
        if (!File.Exists(path)) throw StudioException.NotFound($"Note \"{slug}\"");
        File.Delete(path);
        await notifier.Changed(nameof(KnowledgeNote), Guid.Empty);
    }

    private static KnowledgeNote Parse(string slug, string text)
    {
        var match = Document().Match(text);
        var front = match.Success ? Reader.Deserialize<FrontMatter?>(match.Groups[1].Value) ?? new() : new FrontMatter();
        var body = (match.Success ? match.Groups[2].Value : text).Trim();
        return new KnowledgeNote(slug, front.Title.Length > 0 ? front.Title : slug, front.Tags, front.Summary, body);
    }
}
