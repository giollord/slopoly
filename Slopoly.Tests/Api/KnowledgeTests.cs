using System.Net;
using System.Net.Http.Json;
using Slopoly.ApiService.Infrastructure;
using Slopoly.ApiService.Studio;
using Slopoly.Contracts;
using static Slopoly.Tests.Api.ApiFixture;

namespace Slopoly.Tests.Api;

/// <summary>knowledge-base scenarios (tasks 2.4).</summary>
public sealed class KnowledgeTests
{
    [Test]
    public async Task NoteRoundTripsAndIsFoundByWordPrefix()
    {
        var client = Client();
        var note = new KnowledgeNote("", "Cracks in wood", ["wear", "Wood"], "Shallow darker grooves.", "Subtract a thin box tagged \"wood crack\".");
        Assert.That((await client.PutAsJsonAsync("/api/knowledge/techniques/test-cracks", note, Json)).IsSuccessStatusCode);
        Assert.That((await client.PutAsJsonAsync("/api/knowledge/objects/test-other", note with { Title = "Roof tiles", Tags = ["roof"], Summary = "Rows.", Body = "Instance tiles." }, Json)).IsSuccessStatusCode);

        var read = await ReadAsync<KnowledgeNote>(await client.GetAsync("/api/knowledge/techniques/test-cracks"));
        Assert.That((read.Title, string.Join(",", read.Tags), read.Summary, read.Body), Is.EqualTo((note.Title, "wear,wood", note.Summary, note.Body)));

        var hits = await ReadAsync<List<KnowledgeHit>>(await client.GetAsync("/api/knowledge?q=crack"));
        Assert.That(hits.Select(h => h.Slug), Is.EqualTo(new[] { "techniques/test-cracks" }));

        Assert.That((await client.DeleteAsync("/api/knowledge/techniques/test-cracks")).IsSuccessStatusCode);
        Assert.That((await client.GetAsync("/api/knowledge/techniques/test-cracks")).StatusCode, Is.EqualTo(HttpStatusCode.NotFound));
    }

    [TestCase("techniques/Upper")]
    [TestCase("techniques/a.b")]
    [TestCase("other/note")]
    [TestCase("no-folder")]
    public async Task SlugsOutsideTheFolderAreRefused(string slug)
    {
        var response = await Client().PutAsJsonAsync($"/api/knowledge/{slug}", new KnowledgeNote("", "t", [], "", "b"), Json);
        Assert.That(response.StatusCode, Is.EqualTo(HttpStatusCode.BadRequest));
    }

    /// <summary>HTTP clients collapse dot segments before sending, so path escapes are checked on the service itself.</summary>
    [TestCase("../escape")]
    [TestCase("techniques/../../escape")]
    [TestCase("techniques%2F..%2F..%2Fescape")]
    public async Task DotSegmentsAreRefused(string slug)
    {
        var service = new KnowledgeService(new SlopolyOptions { KnowledgeDir = Path.GetTempPath() }, null!);
        await Assert.ThatAsync(() => service.ReadAsync(slug), Throws.TypeOf<StudioException>());
    }

    [Test]
    public async Task NestedNoteThroughMcp()
    {
        await using var client = await McpToolsTests.ConnectAsync();
        var args = new Dictionary<string, object?>
        {
            ["slug"] = "objects/test-mcp-crate", ["title"] = "Crates", ["tags"] = new[] { "crate" }, ["summary"] = "Boxes.", ["body"] = "Inset the top.",
        };
        var written = await McpToolsTests.CallAsync(client, "write_knowledge", args);
        Assert.That(written.GetProperty("slug").GetString(), Is.EqualTo("objects/test-mcp-crate"));
        var read = await McpToolsTests.CallAsync(client, "read_knowledge", new() { ["slug"] = "objects/test-mcp-crate" });
        Assert.That(read.GetProperty("title").GetString(), Is.EqualTo("Crates"));
        Assert.That((await Client().DeleteAsync("/api/knowledge/objects/test-mcp-crate")).IsSuccessStatusCode);
    }

    /// <summary>The notes shipped in the repository parse, have a title, tags and summary, and answer a typical search.</summary>
    [Test]
    public async Task ShippedNotesAreComplete()
    {
        var root = new DirectoryInfo(AppContext.BaseDirectory);
        while (!File.Exists(Path.Combine(root.FullName, "Slopoly.slnx"))) root = root.Parent!;
        var service = new KnowledgeService(new SlopolyOptions { KnowledgeDir = Path.Combine(root.FullName, "knowledge") }, null!);
        var notes = await service.ListAsync();
        Assert.That(notes, Is.Not.Empty);
        Assert.That(notes, Has.All.Matches<KnowledgeNote>(n => n.Title != n.Slug && n.Tags.Count > 0 && n.Summary.Length > 0));
        Assert.That(notes.Select(n => n.Slug.Split('/')[0]).Distinct(), Is.EquivalentTo(KnowledgeService.Folders));
        foreach (var (query, slug) in new[]
                 {
                     ("open container cavity", "techniques/hollow-containers"), ("cracks chips", "techniques/wear-and-imperfections"),
                     ("spoked wheel", "techniques/wheeled-objects"), ("branch", "techniques/organic-shapes"),
                     ("bark", "techniques/surface-texture"), ("hole", "techniques/holes-and-openings"),
                     ("vase", "techniques/lathed-shapes"), ("leaves", "techniques/foliage"), ("cart", "objects/cart"),
                 })
            Assert.That((await service.SearchAsync(query)).First().Slug, Is.EqualTo(slug), query);
    }
}
