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
        Assert.That((await client.PutAsJsonAsync("/api/knowledge/test-cracks", note, Json)).IsSuccessStatusCode);
        Assert.That((await client.PutAsJsonAsync("/api/knowledge/test-other", note with { Title = "Roof tiles", Tags = ["roof"], Summary = "Rows.", Body = "Instance tiles." }, Json)).IsSuccessStatusCode);

        var read = await ReadAsync<KnowledgeNote>(await client.GetAsync("/api/knowledge/test-cracks"));
        Assert.That((read.Title, string.Join(",", read.Tags), read.Summary, read.Body), Is.EqualTo((note.Title, "wear,wood", note.Summary, note.Body)));

        var hits = await ReadAsync<List<KnowledgeHit>>(await client.GetAsync("/api/knowledge?q=crack"));
        Assert.That(hits.Select(h => h.Slug), Is.EqualTo(new[] { "test-cracks" }));

        Assert.That((await client.DeleteAsync("/api/knowledge/test-cracks")).IsSuccessStatusCode);
        Assert.That((await client.GetAsync("/api/knowledge/test-cracks")).StatusCode, Is.EqualTo(HttpStatusCode.NotFound));
    }

    [TestCase("../escape")]
    [TestCase("Upper")]
    [TestCase("a.b")]
    public async Task SlugsOutsideTheFolderAreRefused(string slug)
    {
        var response = await Client().PutAsJsonAsync($"/api/knowledge/{Uri.EscapeDataString(slug)}", new KnowledgeNote("", "t", [], "", "b"), Json);
        Assert.That(response.StatusCode, Is.EqualTo(HttpStatusCode.BadRequest));
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
        Assert.That((await service.SearchAsync("cart bed hole")).First().Slug, Is.EqualTo("hollow-containers"));
        Assert.That((await service.SearchAsync("cracks chips")).First().Slug, Is.EqualTo("wear-and-imperfections"));
    }
}
