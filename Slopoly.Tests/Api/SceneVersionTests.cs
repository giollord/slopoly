using System.Net.Http.Json;
using System.Text.Json;
using System.Text.Json.Nodes;
using Slopoly.Contracts;
using static Slopoly.Tests.Api.ApiFixture;

namespace Slopoly.Tests.Api;

/// <summary>scenes: variants, version choices and Refresh (tasks 3.1, 3.2).</summary>
public sealed class SceneVersionTests
{
    private static HttpClient Http => Client();

    private static async Task<ProgramVersion> BuiltVersionAsync(Guid assetId, Guid? variantId, string source, bool build = true)
    {
        var url = $"/api/assets/{assetId}/programs" + (variantId is { } v ? $"?variantId={v}" : "");
        var result = await ReadAsync<JsonObject>(await Http.PostAsJsonAsync(url, new ProgramSubmit(source, null), Json));
        var jobId = result["job"]!["id"]!.GetValue<Guid>();
        await TakeJobAsync(JobKinds.Build, jobId);
        if (build)
        {
            await PublishEventAsync(JobKinds.Build, jobId, "succeeded", new JsonObject
            {
                ["glbFileId"] = await UploadAsync([1], "model.glb"), ["validated"] = true, ["report"] = new JsonObject(), ["paletteEntryIds"] = new JsonArray(),
            });
            await WaitForJobAsync(jobId, j => j.State == JobState.Succeeded);
        }
        return result["version"].Deserialize<ProgramVersion>(Json)!;
    }

    private static async Task<List<Guid>> PlacedGlbsAsync(Guid packId, SceneEdit edit)
    {
        var scene = await ReadAsync<Scene>(await Http.PutAsJsonAsync($"/api/packs/{packId}/scenes", edit, Json));
        var job = (await ReadAsync<List<Job>>(await Http.GetAsync($"/api/jobs?packId={packId}&kind={JobKinds.Scene}")))
            .First(j => j.Inputs["sceneId"]!.GetValue<Guid>() == scene.Id);
        var message = await TakeJobAsync(JobKinds.Scene, job.Id);
        return message.Inputs["placements"]!.AsArray().Select(p => p!["glbFileId"]!.GetValue<Guid>()).ToList();
    }

    private static async Task<Guid> GlbOfAsync(Guid versionId) =>
        (await ReadAsync<Page<Build>>(await Http.GetAsync($"/api/assets/{(await ReadAsync<ProgramVersion>(await Http.GetAsync($"/api/programs/{versionId}"))).AssetId}/builds?take=200&variantId={(await ReadAsync<ProgramVersion>(await Http.GetAsync($"/api/programs/{versionId}"))).VariantId}")))
        .Items.First(b => b.ProgramVersionId == versionId).GlbFileId!.Value;

    [Test]
    public async Task VersionChoiceAppliesToAllPlacementsOfTheVariant()
    {
        var pack = await CreatePackAsync();
        var cart = await ReadAsync<Asset>(await Http.PostAsJsonAsync($"/api/packs/{pack.Id}/assets", new AssetCreate("cart", ""), Json));
        var v1 = await BuiltVersionAsync(cart.Id, null, "part('a', box(1, 1, 1))");
        var v2 = await BuiltVersionAsync(cart.Id, null, "part('b', box(1, 1, 1))");
        List<ScenePlacement> carts = [.. Enumerable.Range(1, 5).Select(i => new ScenePlacement($"cart {i}", cart.Id, [i * 2.0, 0, 0]))];

        var current = await PlacedGlbsAsync(pack.Id, new SceneEdit("square", null, carts));
        Assert.That(current, Has.All.EqualTo(await GlbOfAsync(v2.Id)));

        var older = await PlacedGlbsAsync(pack.Id, new SceneEdit("square", null, carts, [new(cart.Id, cart.DefaultVariantId, v1.Id)]));
        Assert.That(older, Has.Count.EqualTo(5).And.All.EqualTo(await GlbOfAsync(v1.Id)));

        // Versions = null keeps the choice; an empty list goes back to current everywhere.
        var kept = await PlacedGlbsAsync(pack.Id, new SceneEdit("square", null, carts));
        Assert.That(kept, Has.All.EqualTo(await GlbOfAsync(v1.Id)));
        var back = await PlacedGlbsAsync(pack.Id, new SceneEdit("square", null, carts, []));
        Assert.That(back, Has.All.EqualTo(await GlbOfAsync(v2.Id)));
    }

    [Test]
    public async Task PlacementsUseTheirOwnVariant()
    {
        var pack = await CreatePackAsync();
        var cart = await ReadAsync<Asset>(await Http.PostAsJsonAsync($"/api/packs/{pack.Id}/assets", new AssetCreate("cart", ""), Json));
        var loaded = await ReadAsync<AssetVariant>(await Http.PostAsJsonAsync($"/api/assets/{cart.Id}/variants", new VariantCreate("loaded"), Json));
        var plain = await BuiltVersionAsync(cart.Id, null, "part('a', box(1, 1, 1))");
        var hay = await BuiltVersionAsync(cart.Id, loaded.Id, "part('b', box(1, 1, 1))");
        var glbs = await PlacedGlbsAsync(pack.Id, new SceneEdit("square", null,
            [new("cart 1", cart.Id, [0, 0, 0]), new("cart 2", cart.Id, [2, 0, 0], VariantId: loaded.Id)]));
        Assert.That(glbs, Is.EqualTo(new[] { await GlbOfAsync(plain.Id), await GlbOfAsync(hay.Id) }));
    }

    [Test]
    public async Task VersionWithoutABuildIsNamedInTheError()
    {
        var pack = await CreatePackAsync();
        var cart = await ReadAsync<Asset>(await Http.PostAsJsonAsync($"/api/packs/{pack.Id}/assets", new AssetCreate("cart", ""), Json));
        await BuiltVersionAsync(cart.Id, null, "part('a', box(1, 1, 1))");
        var unbuilt = await BuiltVersionAsync(cart.Id, null, "part('b', box(1, 1, 1))", build: false);
        var refused = await Http.PutAsJsonAsync($"/api/packs/{pack.Id}/scenes",
            new SceneEdit("square", null, [new("cart 1", cart.Id, [0, 0, 0])], [new(cart.Id, cart.DefaultVariantId, unbuilt.Id)]), Json);
        Assert.That(refused.StatusCode, Is.EqualTo(HttpStatusCode.BadRequest));
        Assert.That(await refused.Content.ReadAsStringAsync(), Does.Contain("cart").And.Contain("default").And.Contain("v2"));
    }

    [Test]
    public async Task SavingAnUnchangedSceneRebuildsIt()
    {
        var pack = await CreatePackAsync();
        var cart = await ReadAsync<Asset>(await Http.PostAsJsonAsync($"/api/packs/{pack.Id}/assets", new AssetCreate("cart", ""), Json));
        await BuiltVersionAsync(cart.Id, null, "part('a', box(1, 1, 1))");
        var edit = new SceneEdit("square", null, [new("cart 1", cart.Id, [0, 0, 0])]);
        await PlacedGlbsAsync(pack.Id, edit);
        await ReadAsync<Scene>(await Http.PutAsJsonAsync($"/api/packs/{pack.Id}/scenes", edit, Json));
        var jobs = await ReadAsync<List<Job>>(await Http.GetAsync($"/api/jobs?packId={pack.Id}&kind={JobKinds.Scene}"));
        Assert.That(jobs, Has.Count.EqualTo(2));
    }
}
