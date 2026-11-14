using System.Net;
using System.Net.Http.Json;
using System.Text.Json.Nodes;
using Slopoly.Contracts;
using static Slopoly.Tests.Api.ApiFixture;

namespace Slopoly.Tests.Api;

/// <summary>Heroes, their views and per-view segmentation (hero-image-and-splat-views tasks 4.2-4.3).</summary>
public sealed class HeroViewsTests
{
    private static HttpClient Http => Client();

    [Test]
    public async Task HeroNeedsAPickedAnchorAndAsksForAThreeQuarterView()
    {
        var pack = await CreatePackAsync();
        var cart = await ReadAsync<Asset>(await Http.PostAsJsonAsync($"/api/packs/{pack.Id}/assets", new AssetCreate("cart", "a hand cart"), Json));
        var refused = await Http.PostAsJsonAsync($"/api/packs/{pack.Id}/generate", new GenerateRequest(Workflows.Hero, cart.Id, null, 2), Json);
        Assert.That(refused.StatusCode, Is.EqualTo(HttpStatusCode.BadRequest));
        Assert.That(await refused.Content.ReadAsStringAsync(), Does.Contain("Pick at least one style anchor"));

        var anchor = await PickedConceptAsync(pack.Id, new GenerateRequest(Workflows.StyleAnchor, null, "a village", 1));
        var hero = await ReadAsync<Job>(await Http.PostAsJsonAsync($"/api/packs/{pack.Id}/generate", new GenerateRequest(Workflows.Hero, cart.Id, null, 2), Json));
        var message = await TakeJobAsync(JobKinds.Comfy, hero.Id);
        Assert.That(message.Operation, Is.EqualTo(Workflows.Hero));
        Assert.That(message.Inputs["prompt"]!.GetValue<string>(), Does.Contain("cart, a hand cart").And.Contain("Three-quarter front view"));
        Assert.That(message.Inputs["references"]!.AsArray().Select(r => r!.GetValue<Guid>()), Is.EqualTo(new[] { anchor.FileId }));
        Assert.That(message.Inputs["count"]!.GetValue<int>(), Is.EqualTo(2));
    }

    [Test]
    public async Task ViewsAreStoredUnderThePickedHeroAndReplacedOnRerender()
    {
        var pack = await CreatePackAsync();
        var cart = await ReadAsync<Asset>(await Http.PostAsJsonAsync($"/api/packs/{pack.Id}/assets", new AssetCreate("cart", "a hand cart"), Json));
        await PickedConceptAsync(pack.Id, new GenerateRequest(Workflows.StyleAnchor, null, "a village", 1));
        var hero = await ConceptAsync(pack.Id, new GenerateRequest(Workflows.Hero, cart.Id, null, 1));

        var unpicked = await Http.PostAsJsonAsync($"/api/concepts/{hero.Id}/views", new ViewsRequest(), Json);
        Assert.That(await unpicked.Content.ReadAsStringAsync(), Does.Contain("Pick the hero image before making its views"));
        await Http.PutAsJsonAsync($"/api/concepts/{hero.Id}/selection", new SelectionEdit(Selection.Picked), Json);

        var job = await ReadAsync<Job>(await Http.PostAsJsonAsync($"/api/concepts/{hero.Id}/views", new ViewsRequest(), Json));
        var message = await TakeJobAsync(JobKinds.Comfy, job.Id);
        Assert.That((message.Operation, message.Inputs["image"]!.GetValue<Guid>()), Is.EqualTo((Workflows.Views, hero.FileId)));
        var seed = message.Inputs["seed"]!.GetValue<long>();
        await SucceedViewsAsync(job.Id, 36, "detected");

        var views = await ReadAsync<List<ConceptImage>>(await Http.GetAsync($"/api/concepts/{hero.Id}/views"));
        Assert.That(views.Select(v => v.View), Is.EqualTo(ViewNames.All));
        Assert.That(views, Has.All.Matches<ConceptImage>(v => v.Kind == ConceptKind.View && v.MaskFileId != null && v.AssetId == cart.Id));
        hero = await ReadAsync<ConceptImage>(await Http.GetAsync($"/api/concepts/{hero.Id}"));
        Assert.That((hero.FrontYaw, hero.Front, hero.ViewsSeed), Is.EqualTo(((double?)36, "detected", (long?)seed)));

        // Segmentation runs on the views, each with its silhouette.
        var segment = await ReadAsync<Job>(await Http.PostAsJsonAsync($"/api/concepts/{hero.Id}/segment", new SegmentRequest(["wheel"]), Json));
        var segmentMessage = await TakeJobAsync(JobKinds.Comfy, segment.Id);
        var inputs = segmentMessage.Inputs["views"]!.AsArray();
        Assert.That(inputs.Select(v => v!["conceptImageId"]!.GetValue<Guid>()), Is.EqualTo(views.Select(v => v.Id)));
        Assert.That(inputs.Select(v => v!["mask"]!.GetValue<Guid>()), Is.EqualTo(views.Select(v => v.MaskFileId!.Value)));
        await PublishEventAsync(JobKinds.Comfy, segment.Id, "succeeded", new JsonObject
        {
            ["masks"] = new JsonArray(views.Select(v => (JsonNode)new JsonObject
            {
                ["conceptImageId"] = v.Id, ["part"] = PartMasks.Object, ["view"] = v.View, ["fileId"] = v.MaskFileId,
                ["bounds"] = new JsonObject { ["x"] = 1, ["y"] = 2, ["width"] = 30, ["height"] = 20 }, ["area"] = 500, ["colors"] = new JsonArray(),
            }).ToArray()),
            ["missing"] = new JsonArray(),
        });
        await WaitForJobAsync(segment.Id, j => j.State == JobState.Succeeded);
        Assert.That(await ReadAsync<List<PartMask>>(await Http.GetAsync($"/api/concepts/{hero.Id}/masks")), Has.Count.EqualTo(4));

        // A corrected front reuses the seed (same splat) and replaces the views and their masks.
        var turned = await ReadAsync<Job>(await Http.PostAsJsonAsync($"/api/concepts/{hero.Id}/views", new ViewsRequest(-54), Json));
        var turnedMessage = await TakeJobAsync(JobKinds.Comfy, turned.Id);
        Assert.That((turnedMessage.Inputs["seed"]!.GetValue<long>(), turnedMessage.Inputs["frontYaw"]!.GetValue<double>()), Is.EqualTo((seed, 306.0)));
        await SucceedViewsAsync(turned.Id, 306, "given");
        var replaced = await ReadAsync<List<ConceptImage>>(await Http.GetAsync($"/api/concepts/{hero.Id}/views"));
        Assert.That(replaced.Select(v => v.Id), Has.None.AnyOf(views.Select(v => v.Id).Cast<object>().ToArray()));
        Assert.That(await ReadAsync<List<PartMask>>(await Http.GetAsync($"/api/concepts/{hero.Id}/masks")), Is.Empty);
    }

    [Test]
    public async Task RejectingAHeroHidesItsViewsAndDeletingRemovesThem()
    {
        var pack = await CreatePackAsync();
        var cart = await ReadAsync<Asset>(await Http.PostAsJsonAsync($"/api/packs/{pack.Id}/assets", new AssetCreate("cart", "a hand cart"), Json));
        await PickedConceptAsync(pack.Id, new GenerateRequest(Workflows.StyleAnchor, null, "a village", 1));
        var hero = await PickedConceptAsync(pack.Id, new GenerateRequest(Workflows.Hero, cart.Id, null, 1));
        var job = await ReadAsync<Job>(await Http.PostAsJsonAsync($"/api/concepts/{hero.Id}/views", new ViewsRequest(), Json));
        await TakeJobAsync(JobKinds.Comfy, job.Id);
        await SucceedViewsAsync(job.Id, 0, "assumed");

        async Task<List<ConceptImage>> Listed() => await ReadAsync<List<ConceptImage>>(await Http.GetAsync($"/api/packs/{pack.Id}/concepts?assetId={cart.Id}"));
        Assert.That((await Listed()).Count(c => c.Kind == ConceptKind.View), Is.EqualTo(4));
        await Http.PutAsJsonAsync($"/api/concepts/{hero.Id}/selection", new SelectionEdit(Selection.Rejected), Json);
        Assert.That(await Listed(), Is.Empty);

        Assert.That((await Http.DeleteAsync($"/api/concepts/{hero.Id}")).IsSuccessStatusCode);
        var all = await ReadAsync<List<ConceptImage>>(await Http.GetAsync($"/api/packs/{pack.Id}/concepts?assetId={cart.Id}&includeRejected=true"));
        Assert.That(all, Is.Empty);
    }

    private static async Task SucceedViewsAsync(Guid jobId, double frontYaw, string front)
    {
        var views = new JsonArray();
        foreach (var view in ViewNames.All)
            views.Add(new JsonObject
            {
                ["view"] = view, ["fileId"] = await UploadAsync([1], $"{view}.png"), ["maskFileId"] = await UploadAsync([2], $"{view}_mask.png"),
                ["width"] = 768, ["height"] = 768,
            });
        await PublishEventAsync(JobKinds.Comfy, jobId, "succeeded", new JsonObject { ["frontYaw"] = frontYaw, ["front"] = front, ["views"] = views });
        await WaitForJobAsync(jobId, j => j.State == JobState.Succeeded);
    }

    private static async Task<ConceptImage> ConceptAsync(Guid packId, GenerateRequest request)
    {
        var job = await ReadAsync<Job>(await Http.PostAsJsonAsync($"/api/packs/{packId}/generate", request, Json));
        await TakeJobAsync(JobKinds.Comfy, job.Id);
        await PublishEventAsync(JobKinds.Comfy, job.Id, "succeeded", new JsonObject
        {
            ["images"] = new JsonArray(new JsonObject { ["fileId"] = await UploadAsync([7], "image.png"), ["width"] = 64, ["height"] = 64 }),
        });
        await WaitForJobAsync(job.Id, j => j.State == JobState.Succeeded);
        var concepts = await ReadAsync<List<ConceptImage>>(await Http.GetAsync($"/api/packs/{packId}/concepts"));
        return concepts.Single(c => c.JobId == job.Id);
    }

    private static async Task<ConceptImage> PickedConceptAsync(Guid packId, GenerateRequest request)
    {
        var concept = await ConceptAsync(packId, request);
        return await ReadAsync<ConceptImage>(await Http.PutAsJsonAsync($"/api/concepts/{concept.Id}/selection", new SelectionEdit(Selection.Picked), Json));
    }
}
