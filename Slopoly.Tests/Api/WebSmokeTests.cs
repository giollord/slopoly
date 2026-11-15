using System.Net.Http.Json;
using System.Text.Json.Nodes;
using Microsoft.AspNetCore.Hosting;
using Microsoft.AspNetCore.Mvc.Testing;
using Slopoly.Contracts;
using Slopoly.Web.Services;
using static Slopoly.Tests.Api.ApiFixture;

namespace Slopoly.Tests.Api;

/// <summary>
/// The web app against the in-memory API: pages are prerendered on the server, so their HTML shows what a page lays
/// out and loads (tasks 4.2, 6.1, 7.3, 7.4, 8.3, 10.3). Interactive behaviour is checked by hand in the running app.
/// </summary>
public sealed class WebSmokeTests
{
    private static WebApplicationFactory<StudioApi> _web = null!;

    [OneTimeSetUp]
    public void Start() =>
        _web = new WebApplicationFactory<StudioApi>().WithWebHostBuilder(b =>
        {
            b.UseSetting("services:apiservice:http:0", "http://localhost:1"); // the event hub stays unreachable: pages still render
            b.ConfigureServices(s => s.AddHttpClient<StudioApi>().ConfigurePrimaryHttpMessageHandler(ApiHandler));
        });

    [OneTimeTearDown]
    public async Task StopAsync() => await _web.DisposeAsync();

    private static async Task<string> PageAsync(string url)
    {
        var response = await _web.CreateClient().GetAsync(url);
        var html = await response.Content.ReadAsStringAsync();
        Assert.That(response.StatusCode, Is.EqualTo(HttpStatusCode.OK), html);
        return html;
    }

    private static async Task<(Pack Pack, Asset Cart, Build Build)> BuiltCartAsync()
    {
        var http = Client();
        var pack = await CreatePackAsync("Smoke village");
        var cart = await ReadAsync<Asset>(await http.PostAsJsonAsync($"/api/packs/{pack.Id}/assets", new AssetCreate("cart", "a hand cart"), Json));
        var submitted = await ReadAsync<JsonObject>(await http.PostAsJsonAsync($"/api/assets/{cart.Id}/programs", new ProgramSubmit("part('a', box(1, 1, 1))", null), Json));
        var jobId = submitted["job"]!["id"]!.GetValue<Guid>();
        await TakeJobAsync(JobKinds.Build, jobId);
        await PublishEventAsync(JobKinds.Build, jobId, "succeeded", new JsonObject
        {
            ["glbFileId"] = await UploadAsync([1], "m.glb"), ["blendFileId"] = await UploadAsync([2], "m.blend"), ["validated"] = true,
            ["report"] = new JsonObject { ["shading"] = new JsonObject { ["merged"] = 0, ["removed"] = 0, ["flipped"] = 2, ["parts"] = new JsonArray() } },
            ["paletteEntryIds"] = new JsonArray(),
        });
        await WaitForJobAsync(jobId, j => j.State == JobState.Succeeded);
        var build = (await ReadAsync<Page<Build>>(await http.GetAsync($"/api/assets/{cart.Id}/builds"))).Items.Single();
        return (pack, cart, build);
    }

    [Test]
    public async Task AssetPageShowsViewerChatAndDownloadsWithSectionsBelow()
    {
        var (_, cart, build) = await BuiltCartAsync();
        var html = await PageAsync($"/assets/{cart.Id}");
        Assert.That(html, Does.Contain("model-viewer-canvas"));
        Assert.That(html, Does.Contain("Message the agent"));
        Assert.That(html, Does.Contain($"/builds/{build.Id}/export").And.Contain($"/builds/{build.Id}/blend"));
        foreach (var section in new[] { "Reference", "Build comparison", "Builds", "Build report", "Manifest", "Program versions", "New program version" })
            Assert.That(html, Does.Contain($">{section}<"), section);
        Assert.That(html, Does.Contain("has no reference hero yet")); // the open Reference section
        Assert.That(html, Does.Not.Contain("Shading defects")); // collapsed sections render no content
        Assert.That(html, Does.Not.Contain("model-viewer-4.4.0"));
    }

    [Test]
    public async Task JobsTabIsPagedWithTheTotal()
    {
        var pack = await CreatePackAsync("Paged village");
        await using (var scope = Services.CreateAsyncScope())
        {
            var db = scope.ServiceProvider.GetRequiredService<Slopoly.ApiService.Data.SlopolyDb>();
            db.Jobs.AddRange(Enumerable.Range(0, 60).Select(i => new Job { Kind = JobKinds.Comfy, Operation = $"op-{i}", PackId = pack.Id, State = JobState.Succeeded }));
            await db.SaveChangesAsync();
        }
        var html = await PageAsync($"/packs/{pack.Id}?tab=jobs");
        Assert.That(html, Does.Contain("mud-table-pagination").And.Contain("Rows per page")); // rows load once interactive
        Assert.That(html, Does.Not.Contain("op-0"));
    }

    [Test]
    public async Task ThreeJsIsMappedForTheViewer()
    {
        var html = await PageAsync("/");
        Assert.That(html, Does.Contain("\"three\":").And.Contain("/lib/three-0.170.0/build/three.module.min.js"));
        var module = await _web.CreateClient().GetAsync("/lib/three-0.170.0/build/three.module.min.js");
        Assert.That(module.StatusCode, Is.EqualTo(HttpStatusCode.OK));
        var viewer = await _web.CreateClient().GetAsync("/js/viewer3d.js");
        Assert.That(viewer.StatusCode, Is.EqualTo(HttpStatusCode.OK));
    }

    [Test]
    public async Task UnchangedSceneOffersRefresh()
    {
        var (pack, cart, _) = await BuiltCartAsync();
        var scene = await ReadAsync<Scene>(await Client().PutAsJsonAsync($"/api/packs/{pack.Id}/scenes",
            new SceneEdit("square", null, [new("cart 1", cart.Id, [0, 0, 0])]), Json));
        var html = await PageAsync($"/scenes/{scene.Id}");
        Assert.That(html, Does.Contain("Refresh").And.Not.Contain("Save and build"));
        Assert.That(html, Does.Contain("Use current everywhere"));
        Assert.That(html, Does.Contain("Message the agent"));
    }
}
