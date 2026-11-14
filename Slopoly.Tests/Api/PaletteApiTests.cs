using System.Net;
using System.Net.Http.Json;
using System.Text.Json.Nodes;
using Slopoly.ApiService.Endpoints;
using Slopoly.ApiService.Studio;
using Slopoly.Contracts;
using static Slopoly.Tests.Api.ApiFixture;

namespace Slopoly.Tests.Api;

/// <summary>surface-palette scenarios on the API (task 7.4).</summary>
public sealed class PaletteApiTests
{
    private static async Task<List<PaletteEntry>> UpsertAsync(Guid packId, params PaletteEntryEdit[] edits) =>
        await ReadAsync<List<PaletteEntry>>(await Client().PutAsJsonAsync($"/api/packs/{packId}/palette/entries", edits, Json));

    /// <summary>A succeeded build of a new asset that samples the given entries, as the geometry worker reports it.</summary>
    private static async Task<Build> FinishedBuildAsync(Guid packId, string assetName, params Guid[] entryIds)
    {
        var client = Client();
        var asset = await ReadAsync<Asset>(await client.PostAsJsonAsync($"/api/packs/{packId}/assets", new AssetCreate(assetName, ""), Json));
        var submitted = await ReadAsync<JsonObject>(await client.PostAsJsonAsync($"/api/assets/{asset.Id}/programs", new ProgramSubmit("part('bed', box(1, 1, 1), color='cart wood')", null), Json));
        var jobId = submitted["job"]!["id"]!.GetValue<Guid>();
        await TakeJobAsync(JobKinds.Build, jobId);
        await PublishEventAsync(JobKinds.Build, jobId, "started");
        await PublishEventAsync(JobKinds.Build, jobId, "succeeded", new JsonObject
        {
            ["glbFileId"] = await UploadAsync([1, 2, 3], "model.glb"),
            ["validated"] = true,
            ["report"] = new JsonObject(),
            ["paletteEntryIds"] = new JsonArray(entryIds.Select(id => (JsonNode)JsonValue.Create(id)).ToArray()),
        });
        await WaitForJobAsync(jobId, j => j.State == JobState.Succeeded);
        return (await ReadAsync<List<Build>>(await client.GetAsync($"/api/assets/{asset.Id}/builds"))).Single();
    }

    /// <summary>A PNG header (signature + IHDR) is enough to carry dimensions.</summary>
    private static byte[] Png(int width, int height) =>
        [0x89, (byte)'P', (byte)'N', (byte)'G', 0x0D, 0x0A, 0x1A, 0x0A, 0, 0, 0, 13, (byte)'I', (byte)'H', (byte)'D', (byte)'R',
         .. BitConverter.GetBytes(System.Buffers.Binary.BinaryPrimitives.ReverseEndianness(width)),
         .. BitConverter.GetBytes(System.Buffers.Binary.BinaryPrimitives.ReverseEndianness(height)), 8, 2, 0, 0, 0];

    private static (int Width, int Height) PngSize(byte[] png) =>
        (System.Buffers.Binary.BinaryPrimitives.ReadInt32BigEndian(png.AsSpan(16)), System.Buffers.Binary.BinaryPrimitives.ReadInt32BigEndian(png.AsSpan(20)));

    [Test]
    public async Task ExportHasTheModelAndOnePngPerVariant()
    {
        var pack = await CreatePackAsync();
        var client = Client();
        var entries = await UpsertAsync(pack.Id, new PaletteEntryEdit("cart wood", null, "#a0703c", null));
        foreach (var name in new[] { "winter", "autumn" })
            await client.PutAsJsonAsync($"/api/packs/{pack.Id}/palette/variants", new VariantEdit(name, [new VariantColorEdit("cart wood", "#ffffff", null)]), Json);
        await Task.Delay(PaletteRenderScheduler.Delay * 3);
        var render = (await ReadAsync<List<Job>>(await client.GetAsync($"/api/jobs?packId={pack.Id}&kind={JobKinds.PaletteRender}"))).First();
        var palette = await ReadAsync<PaletteView>(await client.GetAsync($"/api/packs/{pack.Id}/palette"));
        await PublishEventAsync(JobKinds.PaletteRender, render.Id, "started");
        await PublishEventAsync(JobKinds.PaletteRender, render.Id, "succeeded", new JsonObject
        {
            ["textureFileId"] = await UploadAsync(Png(256, 256), "palette.png"),
            ["variants"] = new JsonObject(await Task.WhenAll(palette.Variants.Select(async v =>
                new KeyValuePair<string, JsonNode?>(v.Id.ToString(), await UploadAsync(Png(256, 256), $"palette_{v.Name}.png"))))),
        });
        await WaitForJobAsync(render.Id, j => j.State == JobState.Succeeded);
        var build = await FinishedBuildAsync(pack.Id, "wooden cart", entries[0].Id);

        var response = await client.GetAsync($"/api/builds/{build.Id}/export");
        using var zip = new System.IO.Compression.ZipArchive(await ReadStreamAsync(response));
        Assert.That(zip.Entries.Select(e => e.FullName).Order(), Is.EqualTo(new[] { "palette_autumn.png", "palette_winter.png", "wooden_cart.glb" }));
        var main = PngSize(await client.GetByteArrayAsync($"/api/files/{(await ReadAsync<Pack>(await client.GetAsync($"/api/packs/{pack.Id}"))).PaletteTextureFileId}"));
        foreach (var entry in zip.Entries.Where(e => e.Name.EndsWith(".png")))
        {
            using var stream = new MemoryStream();
            await entry.Open().CopyToAsync(stream);
            Assert.That(PngSize(stream.ToArray()), Is.EqualTo(main));
        }
    }

    private static async Task<Stream> ReadStreamAsync(HttpResponseMessage response)
    {
        if (!response.IsSuccessStatusCode) Assert.Fail($"{(int)response.StatusCode}: {await response.Content.ReadAsStringAsync()}");
        return new MemoryStream(await response.Content.ReadAsByteArrayAsync());
    }

    [Test]
    public async Task DuplicateRoleIsRefusedAndSlotsStayFixed()
    {
        var pack = await CreatePackAsync();
        var first = await UpsertAsync(pack.Id, new PaletteEntryEdit("wall base", null, "#aa8866", null), new PaletteEntryEdit("wall accent", null, "#553322", null));
        var response = await Client().PostAsJsonAsync($"/api/packs/{pack.Id}/palette/entries", new PaletteEntryEdit("Wall Base", null, "#000000", null), Json);
        Assert.That(response.StatusCode, Is.EqualTo(HttpStatusCode.Conflict));

        var recoloured = await UpsertAsync(pack.Id, new PaletteEntryEdit("wall base", null, "#ff0000", null), new PaletteEntryEdit("leaf 1", PaletteKind.Gradient, "#00aa00", "#88ff88"));
        Assert.That(recoloured[0].Slot, Is.EqualTo(first[0].Slot));
        Assert.That(recoloured[1].Slot, Is.EqualTo(0), "gradients have their own slots");
        Assert.That(recoloured[0].Color, Is.EqualTo("#ff0000"));
    }

    [Test]
    public async Task EntryUsedByABuildCannotBeDeleted()
    {
        var pack = await CreatePackAsync();
        var client = Client();
        var entries = await UpsertAsync(pack.Id, new PaletteEntryEdit("cart wood", null, "#a0703c", null), new PaletteEntryEdit("unused", null, "#000000", null));
        await FinishedBuildAsync(pack.Id, "cart", entries[0].Id);

        var refused = await client.DeleteAsync($"/api/palette/entries/{entries[0].Id}");
        Assert.That(refused.StatusCode, Is.EqualTo(HttpStatusCode.Conflict));
        Assert.That(await refused.Content.ReadAsStringAsync(), Does.Contain("cart"));
        Assert.That((await client.DeleteAsync($"/api/palette/entries/{entries[1].Id}")).IsSuccessStatusCode);
    }

    [Test]
    public async Task VariantFallsBackToMainColourForNewRoles()
    {
        var pack = await CreatePackAsync();
        var client = Client();
        await UpsertAsync(pack.Id, new PaletteEntryEdit("roof", null, "#884422", null));
        await ReadAsync<VariantView>(await client.PutAsJsonAsync($"/api/packs/{pack.Id}/palette/variants",
            new VariantEdit("winter", [new VariantColorEdit("roof", "#eeeeff", null)]), Json));
        await UpsertAsync(pack.Id, new PaletteEntryEdit("door", null, "#553311", null));

        var palette = await ReadAsync<PaletteView>(await client.GetAsync($"/api/packs/{pack.Id}/palette"));
        var winter = palette.Variants.Single().Entries.ToDictionary(e => e.Role, e => e.Color);
        Assert.That(winter, Is.EqualTo(new Dictionary<string, string> { ["roof"] = "#eeeeff", ["door"] = "#553311" }));
    }

    [Test]
    public async Task EditsAreDebouncedIntoOneRenderJob()
    {
        var pack = await CreatePackAsync();
        foreach (var color in new[] { "#111111", "#222222", "#333333" })
            await UpsertAsync(pack.Id, new PaletteEntryEdit("wall base", null, color, null));
        await Task.Delay(PaletteRenderScheduler.Delay * 3);
        var jobs = await ReadAsync<List<Job>>(await Client().GetAsync($"/api/jobs?packId={pack.Id}&kind={JobKinds.PaletteRender}"));
        Assert.That(jobs, Has.Count.EqualTo(1));
        var message = await TakeJobAsync(JobKinds.PaletteRender, jobs[0].Id);
        Assert.That(message.Inputs["main"]![0]!["color"]!.GetValue<string>(), Is.EqualTo("#333333"));
    }

    [Test]
    public async Task BuildsSeeOnlyMainColours()
    {
        var pack = await CreatePackAsync();
        var client = Client();
        await UpsertAsync(pack.Id, new PaletteEntryEdit("roof", null, "#884422", null));
        await client.PutAsJsonAsync($"/api/packs/{pack.Id}/palette/variants", new VariantEdit("winter", [new VariantColorEdit("roof", "#eeeeff", null)]), Json);
        var asset = await ReadAsync<Asset>(await client.PostAsJsonAsync($"/api/packs/{pack.Id}/assets", new AssetCreate("hut", ""), Json));
        var submitted = await ReadAsync<JsonObject>(await client.PostAsJsonAsync($"/api/assets/{asset.Id}/programs", new ProgramSubmit("part('roof', box(1, 1, 1), color='roof')", null), Json));
        var build = await TakeJobAsync(JobKinds.Build, submitted["job"]!["id"]!.GetValue<Guid>());
        var palette = build.Inputs["palette"]!.AsArray();
        Assert.That(palette.Select(e => e!["color"]!.GetValue<string>()), Is.EqualTo(new[] { "#884422" }));
    }
}
