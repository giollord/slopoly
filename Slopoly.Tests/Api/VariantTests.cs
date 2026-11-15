using System.Net.Http.Json;
using System.Text.Json;
using System.Text.Json.Nodes;
using Slopoly.Contracts;
using static Slopoly.Tests.Api.ApiFixture;
using static Slopoly.Tests.Api.HeroViewsTests;

namespace Slopoly.Tests.Api;

/// <summary>asset-variants scenarios (tasks 2.1-2.4).</summary>
public sealed class VariantTests
{
    private static HttpClient Http => Client();

    private static async Task<(Pack Pack, Asset Asset)> CartAsync(int? budget = null)
    {
        var pack = await CreatePackAsync();
        var cart = await ReadAsync<Asset>(await Http.PostAsJsonAsync($"/api/packs/{pack.Id}/assets", new AssetCreate("cart", "a hand cart", budget), Json));
        return (pack, cart);
    }

    private static Task<List<AssetVariant>> VariantsAsync(Guid assetId) =>
        Http.GetAsync($"/api/assets/{assetId}/variants").ContinueWith(t => ReadAsync<List<AssetVariant>>(t.Result)).Unwrap();

    private static async Task<AssetVariant> CreateAsync(Guid assetId, VariantCreate create) =>
        await ReadAsync<AssetVariant>(await Http.PostAsJsonAsync($"/api/assets/{assetId}/variants", create, Json));

    private static async Task<(ProgramVersion Version, Guid JobId)> SubmitAsync(Guid assetId, Guid? variantId, string source)
    {
        var url = $"/api/assets/{assetId}/programs" + (variantId is { } v ? $"?variantId={v}" : "");
        var result = await ReadAsync<JsonObject>(await Http.PostAsJsonAsync(url, new ProgramSubmit(source, null), Json));
        return (result["version"].Deserialize<ProgramVersion>(Json)!, result["job"]!["id"]!.GetValue<Guid>());
    }

    private static async Task SucceedBuildAsync(Guid jobId, bool validated = true)
    {
        await TakeJobAsync(JobKinds.Build, jobId);
        await PublishEventAsync(JobKinds.Build, jobId, "succeeded", new JsonObject
        {
            ["glbFileId"] = await UploadAsync([1], "model.glb"), ["validated"] = validated, ["report"] = new JsonObject(), ["paletteEntryIds"] = new JsonArray(),
        });
        await WaitForJobAsync(jobId, j => j.State == JobState.Succeeded);
    }

    /// <summary>A picked hero with views in the variant (the default variant when null).</summary>
    private static async Task<ConceptImage> ReferenceAsync(Guid packId, Guid assetId, Guid? variantId)
    {
        var hero = await ConceptAsync(packId, new GenerateRequest(Workflows.Hero, assetId, null, 1, VariantId: variantId));
        hero = await ReadAsync<ConceptImage>(await Http.PutAsJsonAsync($"/api/concepts/{hero.Id}/selection", new SelectionEdit(Selection.Picked), Json));
        var views = await ReadAsync<Job>(await Http.PostAsJsonAsync($"/api/concepts/{hero.Id}/views", new ViewsRequest(), Json));
        await TakeJobAsync(JobKinds.Comfy, views.Id);
        await SucceedViewsAsync(views.Id, 0, "detected");
        return hero;
    }

    [Test]
    public async Task NewAssetHasADefaultVariantAndVariantsKeepTheirOwnHistory()
    {
        var (_, cart) = await CartAsync(1500);
        var variants = await VariantsAsync(cart.Id);
        Assert.That(variants.Select(v => v.Name), Is.EqualTo(new[] { "default" }));
        Assert.That(cart.DefaultVariantId, Is.EqualTo(variants[0].Id));

        var loaded = await CreateAsync(cart.Id, new VariantCreate("loaded"));
        Assert.That((await VariantsAsync(cart.Id)).Select(v => v.Name), Is.EqualTo(new[] { "default", "loaded" }));
        var duplicate = await Http.PostAsJsonAsync($"/api/assets/{cart.Id}/variants", new VariantCreate("loaded"), Json);
        Assert.That(duplicate.StatusCode, Is.EqualTo(HttpStatusCode.Conflict));

        // Omitting the variant acts on the default one; numbering is per variant; the budget is shared.
        for (var i = 0; i < 3; i++) await SubmitAsync(cart.Id, null, $"part('a{i}', box(1, 1, 1))");
        var (first, job) = await SubmitAsync(cart.Id, loaded.Id, "part('b', box(1, 1, 1))");
        Assert.That(first.Number, Is.EqualTo(1));
        Assert.That(first.VariantId, Is.EqualTo(loaded.Id));
        var message = await TakeJobAsync(JobKinds.Build, job);
        Assert.That(message.Inputs["polyBudget"]!.GetValue<int>(), Is.EqualTo(1500));
        var defaults = await ReadAsync<Page<ProgramVersion>>(await Http.GetAsync($"/api/assets/{cart.Id}/programs"));
        var loadedPrograms = await ReadAsync<Page<ProgramVersion>>(await Http.GetAsync($"/api/assets/{cart.Id}/programs?variantId={loaded.Id}"));
        Assert.That(defaults.Items.Select(v => v.Number), Is.EqualTo(new[] { 3, 2, 1 }));
        Assert.That(loadedPrograms.Items.Select(v => v.Number), Is.EqualTo(new[] { 1 }));
    }

    [Test]
    public async Task VariantCopiedFromAnotherGetsItsManifestAndCurrentProgram()
    {
        var (_, cart) = await CartAsync();
        var manifest = JsonNode.Parse("""{ "parts": [ { "name": "bed" } ] }""");
        await ReadAsync<Manifest>(await Http.PutAsJsonAsync($"/api/assets/{cart.Id}/manifest", manifest));
        var (current, _) = await SubmitAsync(cart.Id, null, "part('bed', box(1, 1, 1))");

        var loaded = await CreateAsync(cart.Id, new VariantCreate("loaded", FromVariantId: cart.DefaultVariantId));
        var programs = await ReadAsync<Page<ProgramVersion>>(await Http.GetAsync($"/api/assets/{cart.Id}/programs?variantId={loaded.Id}"));
        Assert.That(programs.Items.Single().Number, Is.EqualTo(1));
        Assert.That(programs.Items.Single().Source, Is.EqualTo(current.Source));
        Assert.That(loaded.CurrentProgramVersionId, Is.EqualTo(programs.Items.Single().Id));

        await ReadAsync<Manifest>(await Http.PutAsJsonAsync($"/api/assets/{cart.Id}/manifest?variantId={loaded.Id}",
            JsonNode.Parse("""{ "parts": [ { "name": "bed" }, { "name": "hay", "parent": "bed" } ] }""")));
        var original = await ReadAsync<Manifest>(await Http.GetAsync($"/api/assets/{cart.Id}/manifest"));
        Assert.That(original.Content["parts"]!.AsArray(), Has.Count.EqualTo(1));
    }

    [Test]
    public async Task BuildsCompareOnlyAgainstTheirVariantsReference()
    {
        var (pack, cart) = await CartAsync();
        await PickedConceptAsync(pack.Id, new GenerateRequest(Workflows.StyleAnchor, null, "a village", 1));
        var loaded = await CreateAsync(cart.Id, new VariantCreate("loaded"));
        var heroA = await ReferenceAsync(pack.Id, cart.Id, null);
        var heroB = await ReferenceAsync(pack.Id, cart.Id, loaded.Id);
        Assert.That(heroB.VariantId, Is.EqualTo(loaded.Id));
        var viewsA = (await ReadAsync<List<ConceptImage>>(await Http.GetAsync($"/api/concepts/{heroA.Id}/views"))).Select(v => v.Id).ToList();
        var viewsB = (await ReadAsync<List<ConceptImage>>(await Http.GetAsync($"/api/concepts/{heroB.Id}/views"))).Select(v => v.Id).ToList();

        var (_, defaultJob) = await SubmitAsync(cart.Id, null, "part('a', box(1, 1, 1))");
        var (_, loadedJob) = await SubmitAsync(cart.Id, loaded.Id, "part('b', box(1, 1, 1))");
        var defaultViews = (await TakeJobAsync(JobKinds.Build, defaultJob)).Inputs["views"]!.AsArray().Select(v => v!["id"]!.GetValue<Guid>());
        var loadedViews = (await TakeJobAsync(JobKinds.Build, loadedJob)).Inputs["views"]!.AsArray().Select(v => v!["id"]!.GetValue<Guid>());
        Assert.That(defaultViews, Is.EquivalentTo(viewsA));
        Assert.That(loadedViews, Is.EquivalentTo(viewsB));
    }

    [Test]
    public async Task VariantWithoutReferenceSaysWhyTheComparisonIsSkipped()
    {
        var (_, cart) = await CartAsync();
        var (_, job) = await SubmitAsync(cart.Id, null, "part('a', box(1, 1, 1))");
        var message = await TakeJobAsync(JobKinds.Build, job);
        Assert.That(message.Inputs["views"]!.AsArray(), Is.Empty);
        Assert.That(message.Inputs["noViewsReason"]!.GetValue<string>(), Is.EqualTo("no reference hero for this variant"));
    }

    [Test]
    public async Task PickingASecondHeroNeedsAChoice()
    {
        var (pack, cart) = await CartAsync();
        await PickedConceptAsync(pack.Id, new GenerateRequest(Workflows.StyleAnchor, null, "a village", 1));
        var heroA = await ReferenceAsync(pack.Id, cart.Id, null);
        var heroC = await ConceptAsync(pack.Id, new GenerateRequest(Workflows.Hero, cart.Id, null, 1));

        var refused = await Http.PutAsJsonAsync($"/api/concepts/{heroC.Id}/selection", new SelectionEdit(Selection.Picked), Json);
        Assert.That(refused.StatusCode, Is.EqualTo(HttpStatusCode.Conflict));
        var problem = await refused.Content.ReadFromJsonAsync<JsonObject>();
        Assert.That(problem!["code"]!.GetValue<string>(), Is.EqualTo(SelectionConflicts.ReferenceExists));
        Assert.That(problem["title"]!.GetValue<string>(), Does.Contain("already has a reference hero"));

        await ReadAsync<ConceptImage>(await Http.PutAsJsonAsync($"/api/concepts/{heroC.Id}/selection",
            new SelectionEdit(Selection.Picked, SelectionConflicts.Replace), Json));
        heroA = await ReadAsync<ConceptImage>(await Http.GetAsync($"/api/concepts/{heroA.Id}"));
        Assert.That(heroA.Selection, Is.EqualTo(Selection.None));
        Assert.That(await ReadAsync<List<ConceptImage>>(await Http.GetAsync($"/api/concepts/{heroA.Id}/views")), Has.Count.EqualTo(4));

        // The other way: a new variant from a further hero; the default keeps C.
        var heroD = await ConceptAsync(pack.Id, new GenerateRequest(Workflows.Hero, cart.Id, null, 1));
        await ReadAsync<ConceptImage>(await Http.PutAsJsonAsync($"/api/concepts/{heroD.Id}/selection",
            new SelectionEdit(Selection.Picked, SelectionConflicts.NewVariant, "rustic"), Json));
        var rustic = (await VariantsAsync(cart.Id)).Single(v => v.Name == "rustic");
        heroD = await ReadAsync<ConceptImage>(await Http.GetAsync($"/api/concepts/{heroD.Id}"));
        Assert.That((heroD.VariantId, heroD.Selection), Is.EqualTo(((Guid?)rustic.Id, Selection.Picked)));
        heroC = await ReadAsync<ConceptImage>(await Http.GetAsync($"/api/concepts/{heroC.Id}"));
        Assert.That((heroC.VariantId, heroC.Selection), Is.EqualTo(((Guid?)cart.DefaultVariantId, Selection.Picked)));
    }

    [Test]
    public async Task VariantFromAHeroMovesItsViews()
    {
        var (pack, cart) = await CartAsync();
        await PickedConceptAsync(pack.Id, new GenerateRequest(Workflows.StyleAnchor, null, "a village", 1));
        var hero = await ReferenceAsync(pack.Id, cart.Id, null);
        var rustic = await CreateAsync(cart.Id, new VariantCreate("rustic", FromHeroId: hero.Id));
        var views = await ReadAsync<List<ConceptImage>>(await Http.GetAsync($"/api/concepts/{hero.Id}/views"));
        Assert.That(views, Has.All.Matches<ConceptImage>(v => v.VariantId == rustic.Id));
        Assert.That((await ReadAsync<ConceptImage>(await Http.GetAsync($"/api/concepts/{hero.Id}"))).VariantId, Is.EqualTo(rustic.Id));
    }

    [Test]
    public async Task DeletingAVariantIsRefusedWhileAScenePlacesIt()
    {
        var (pack, cart) = await CartAsync();
        var loaded = await CreateAsync(cart.Id, new VariantCreate("loaded"));
        var (_, job) = await SubmitAsync(cart.Id, loaded.Id, "part('a', box(1, 1, 1))");
        await SucceedBuildAsync(job);
        await ReadAsync<Scene>(await Http.PutAsJsonAsync($"/api/packs/{pack.Id}/scenes",
            new SceneEdit("market square", null, [new("cart 1", cart.Id, [0, 0, 0], VariantId: loaded.Id)]), Json));

        var refused = await Http.DeleteAsync($"/api/variants/{loaded.Id}");
        Assert.That(refused.StatusCode, Is.EqualTo(HttpStatusCode.Conflict));
        Assert.That(await refused.Content.ReadAsStringAsync(), Does.Contain("market square"));

        var only = await CartAsync();
        var last = await Http.DeleteAsync($"/api/variants/{only.Asset.DefaultVariantId}");
        Assert.That(last.StatusCode, Is.EqualTo(HttpStatusCode.Conflict));
    }

    [Test]
    public async Task AssetStatusIsTheFurthestOfItsVariants()
    {
        var (_, cart) = await CartAsync();
        var loaded = await CreateAsync(cart.Id, new VariantCreate("loaded"));
        var (_, job) = await SubmitAsync(cart.Id, null, "part('a', box(1, 1, 1))");
        await SucceedBuildAsync(job, validated: true);
        await ReadAsync<Manifest>(await Http.PutAsJsonAsync($"/api/assets/{cart.Id}/manifest?variantId={loaded.Id}",
            JsonNode.Parse("""{ "parts": [ { "name": "bed" } ] }""")));
        var asset = await ReadAsync<Asset>(await Http.GetAsync($"/api/assets/{cart.Id}"));
        var variants = await VariantsAsync(cart.Id);
        Assert.That(asset.Status, Is.EqualTo(AssetStatus.Validated));
        Assert.That(variants.Single(v => v.Name == "loaded").Status, Is.EqualTo(AssetStatus.Manifest));
        Assert.That(variants.Single(v => v.Name == "default").Status, Is.EqualTo(AssetStatus.Validated));
    }

    [Test]
    public async Task McpProgramForANamedVariantLeavesTheDefaultUnchanged()
    {
        var (_, cart) = await CartAsync();
        await using var client = await McpToolsTests.ConnectAsync();
        var loaded = await McpToolsTests.CallAsync(client, "create_variant", new() { ["assetId"] = cart.Id, ["name"] = "loaded" });
        var loadedId = loaded.GetProperty("id").GetGuid();
        await McpToolsTests.CallAsync(client, "submit_program", new() { ["assetId"] = cart.Id, ["source"] = "part('a', box(1, 1, 1))", ["variantId"] = loadedId });
        var listed = await McpToolsTests.CallAsync(client, "list_variants", new() { ["assetId"] = cart.Id });
        Assert.That(listed.GetArrayLength(), Is.EqualTo(2));
        var defaults = await ReadAsync<Page<ProgramVersion>>(await Http.GetAsync($"/api/assets/{cart.Id}/programs"));
        Assert.That(defaults.Total, Is.Zero);
        var variant = await ReadAsync<AssetVariant>(await Http.GetAsync($"/api/variants/{loadedId}"));
        Assert.That(variant.CurrentProgramVersionId, Is.Not.Null);
        await McpToolsTests.CallAsync(client, "update_variant", new() { ["variantId"] = loadedId, ["makeDefault"] = true });
        Assert.That((await ReadAsync<Asset>(await Http.GetAsync($"/api/assets/{cart.Id}"))).DefaultVariantId, Is.EqualTo(loadedId));
    }
}
