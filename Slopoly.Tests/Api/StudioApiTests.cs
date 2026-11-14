using System.Net;
using System.Net.Http.Json;
using System.Text.Json.Nodes;
using Microsoft.AspNetCore.SignalR.Client;
using Slopoly.ApiService.Endpoints;
using Slopoly.ApiService.Studio;
using Slopoly.Contracts;
using static Slopoly.Tests.Api.ApiFixture;

namespace Slopoly.Tests.Api;

/// <summary>asset-packs scenarios and file storage (tasks 2.2-2.5).</summary>
public sealed class StudioApiTests
{
    [Test]
    public async Task UploadedFileDownloadsWithSameBytes()
    {
        var bytes = Enumerable.Range(0, 5000).Select(i => (byte)(i * 7)).ToArray();
        var id = await UploadAsync(bytes, "mask.png");
        var downloaded = await Client().GetByteArrayAsync($"/api/files/{id}");
        Assert.That(downloaded, Is.EqualTo(bytes));
    }

    [Test]
    public async Task UploadWithoutWorkerKeyIsRejected()
    {
        using var form = new MultipartFormDataContent { { new ByteArrayContent([1, 2, 3]), "file", "x.bin" } };
        var response = await Client().PostAsync("/worker/files", form);
        Assert.That(response.StatusCode, Is.EqualTo(HttpStatusCode.Unauthorized));
    }

    [Test]
    public async Task CreatePackWithReferencesAndEditStyle()
    {
        var pack = await CreatePackAsync("Gnome village");
        var client = Client();
        foreach (var name in new[] { "ref1.png", "ref2.png" })
        {
            using var form = new MultipartFormDataContent { { new ByteArrayContent([9, 9, 9]), "file", name } };
            await ReadAsync<StyleReference>(await client.PostAsync($"/api/packs/{pack.Id}/style-references", form));
        }
        var references = await ReadAsync<List<StyleReference>>(await client.GetAsync($"/api/packs/{pack.Id}/style-references"));
        Assert.That(references, Has.Count.EqualTo(2));

        var edited = await ReadAsync<Pack>(await client.PatchAsJsonAsync($"/api/packs/{pack.Id}", new PackEdit(null, null, "muted, painterly", null), Json));
        Assert.That(edited.StyleText, Is.EqualTo("muted, painterly"));

        await client.DeleteAsync($"/api/style-references/{references[0].Id}");
        references = await ReadAsync<List<StyleReference>>(await client.GetAsync($"/api/packs/{pack.Id}/style-references"));
        Assert.That(references, Has.Count.EqualTo(1));
    }

    [Test]
    public async Task GeneratedConceptsCanBeRejectedAndAreHiddenByDefault()
    {
        var pack = await CreatePackAsync();
        var client = Client();
        var job = await ReadAsync<Job>(await client.PostAsJsonAsync($"/api/packs/{pack.Id}/generate",
            new GenerateRequest(Workflows.StyleAnchor, null, "a gnome village", 2), Json));
        var message = await TakeJobAsync(JobKinds.Comfy, job.Id);
        Assert.That(message.Inputs["prompt"]!.GetValue<string>(), Does.Contain("quirky, vibrant").And.Contain("a gnome village"));

        var files = new[] { await UploadAsync([1], "a.png"), await UploadAsync([2], "b.png") };
        await PublishEventAsync(JobKinds.Comfy, job.Id, "started");
        await PublishEventAsync(JobKinds.Comfy, job.Id, "succeeded", new JsonObject
        {
            ["images"] = new JsonArray(files.Select(f => (JsonNode)new JsonObject { ["fileId"] = f, ["width"] = 64, ["height"] = 64 }).ToArray()),
        });
        await WaitForJobAsync(job.Id, j => j.State == JobState.Succeeded);

        var concepts = await ReadAsync<List<ConceptImage>>(await client.GetAsync($"/api/packs/{pack.Id}/concepts"));
        Assert.That(concepts.Select(c => c.Selection), Is.All.EqualTo(Selection.None));
        await client.PutAsJsonAsync($"/api/concepts/{concepts[0].Id}/selection", new SelectionEdit(Selection.Rejected), Json);

        var visible = await ReadAsync<List<ConceptImage>>(await client.GetAsync($"/api/packs/{pack.Id}/concepts"));
        var all = await ReadAsync<List<ConceptImage>>(await client.GetAsync($"/api/packs/{pack.Id}/concepts?includeRejected=true"));
        Assert.That(visible.Select(c => c.Id), Is.EqualTo(new[] { concepts[1].Id }));
        Assert.That(all, Has.Count.EqualTo(2));

        // More variants: the same generation with a fresh seed; new images join the old ones, undecided.
        await client.PutAsJsonAsync($"/api/concepts/{concepts[1].Id}/selection", new SelectionEdit(Selection.Picked), Json);
        var more = await ReadAsync<Job>(await client.PostAsync($"/api/concepts/{concepts[1].Id}/more?count=3", null));
        var moreMessage = await TakeJobAsync(JobKinds.Comfy, more.Id);
        Assert.That(more.Operation, Is.EqualTo(Workflows.StyleAnchor));
        Assert.That(moreMessage.Inputs["prompt"]!.GetValue<string>(), Is.EqualTo(message.Inputs["prompt"]!.GetValue<string>()));
        Assert.That((moreMessage.Inputs["count"]!.GetValue<int>(), moreMessage.Inputs["seed"]), Is.EqualTo((3, (JsonNode?)null)));
        await PublishEventAsync(JobKinds.Comfy, more.Id, "succeeded", new JsonObject
        {
            ["images"] = new JsonArray(new JsonObject { ["fileId"] = await UploadAsync([3], "c.png"), ["width"] = 64, ["height"] = 64 }),
        });
        await WaitForJobAsync(more.Id, j => j.State == JobState.Succeeded);
        all = await ReadAsync<List<ConceptImage>>(await client.GetAsync($"/api/packs/{pack.Id}/concepts?includeRejected=true"));
        Assert.That(all.Select(c => c.Selection), Is.EquivalentTo(new[] { Selection.Rejected, Selection.Picked, Selection.None }));
    }

    [Test]
    public async Task ManifestWithUnknownParentIsRejected()
    {
        var pack = await CreatePackAsync();
        var asset = await ReadAsync<Asset>(await Client().PostAsJsonAsync($"/api/packs/{pack.Id}/assets", new AssetCreate("wooden cart", "a cart"), Json));
        var manifest = JsonNode.Parse("""{ "parts": [ { "name": "bed" }, { "name": "wheel_L", "parent": "axel" } ] }""")!;
        var response = await Client().PutAsJsonAsync($"/api/assets/{asset.Id}/manifest", manifest);
        Assert.That(response.StatusCode, Is.EqualTo(HttpStatusCode.BadRequest));
        Assert.That(await response.Content.ReadAsStringAsync(), Does.Contain("unknown parent").And.Contain("axel"));
    }

    [Test]
    public async Task EarlierProgramVersionCanBecomeCurrentAgain()
    {
        var pack = await CreatePackAsync();
        var client = Client();
        var asset = await ReadAsync<Asset>(await client.PostAsJsonAsync($"/api/packs/{pack.Id}/assets", new AssetCreate("cart", ""), Json));
        await ReadAsync<Manifest>(await client.PutAsJsonAsync($"/api/assets/{asset.Id}/manifest",
            JsonNode.Parse("""{ "parts": [ { "name": "bed" }, { "name": "axle", "parent": "bed", "connections": [ { "to": "bed", "type": "rotate", "axis": "x" } ] } ] }""")));

        var first = await ReadAsync<JsonObject>(await client.PostAsJsonAsync($"/api/assets/{asset.Id}/programs", new ProgramSubmit("part('bed', box(1, 1, 1))", "v1"), Json));
        var second = await ReadAsync<JsonObject>(await client.PostAsJsonAsync($"/api/assets/{asset.Id}/programs", new ProgramSubmit("raise Exception()", "broken"), Json));
        var firstVersion = first["version"]!["id"]!.GetValue<Guid>();
        var secondJob = second["job"]!["id"]!.GetValue<Guid>();
        var build = await TakeJobAsync(JobKinds.Build, secondJob);
        Assert.That(build.Inputs["source"]!.GetValue<string>(), Is.EqualTo("raise Exception()"));
        await PublishEventAsync(JobKinds.Build, secondJob, "failed", error: "line 1: Exception");
        await WaitForJobAsync(secondJob, j => j.State == JobState.Failed);

        var versions = await ReadAsync<List<ProgramVersion>>(await client.GetAsync($"/api/assets/{asset.Id}/programs"));
        Assert.That(versions.Select(v => v.Number), Is.EqualTo(new[] { 2, 1 }));
        var current = await ReadAsync<Asset>(await client.PutAsJsonAsync($"/api/assets/{asset.Id}/current-version", new CurrentVersionEdit(firstVersion), Json));
        Assert.That(current.CurrentProgramVersionId, Is.EqualTo(firstVersion));
    }

    [Test]
    public async Task HubAnnouncesNewPack()
    {
        await using var hub = await HubAsync();
        var received = new TaskCompletionSource<ChangeEvent>();
        hub.On<ChangeEvent>(Realtime.Changed, e => { if (e.Entity == nameof(Pack)) received.TrySetResult(e); });
        var pack = await CreatePackAsync();
        var change = await received.Task.WaitAsync(TimeSpan.FromSeconds(5));
        Assert.That(change.Id, Is.EqualTo(pack.Id));
    }
}
