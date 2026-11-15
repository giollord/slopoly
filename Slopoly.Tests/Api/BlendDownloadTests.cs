using System.IO.Compression;
using System.Net.Http.Json;
using System.Text.Json.Nodes;
using Slopoly.ApiService.Data;
using Slopoly.Contracts;
using static Slopoly.Tests.Api.ApiFixture;

namespace Slopoly.Tests.Api;

/// <summary>Blender file download (task 10.2).</summary>
public sealed class BlendDownloadTests
{
    private static HttpClient Http => Client();

    private static async Task<(Pack Pack, Build Build)> BuildAsync(bool withBlend)
    {
        var pack = await CreatePackAsync();
        var cart = await ReadAsync<Asset>(await Http.PostAsJsonAsync($"/api/packs/{pack.Id}/assets", new AssetCreate("wooden cart", ""), Json));
        var submitted = await ReadAsync<JsonObject>(await Http.PostAsJsonAsync($"/api/assets/{cart.Id}/programs", new ProgramSubmit("part('a', box(1, 1, 1))", null), Json));
        var jobId = submitted["job"]!["id"]!.GetValue<Guid>();
        await TakeJobAsync(JobKinds.Build, jobId);
        var outputs = new JsonObject
        {
            ["glbFileId"] = await UploadAsync([1], "model.glb"), ["validated"] = true, ["report"] = new JsonObject(), ["paletteEntryIds"] = new JsonArray(),
        };
        if (withBlend) outputs["blendFileId"] = await UploadAsync([66, 76, 69, 78, 68], "model.blend");
        await PublishEventAsync(JobKinds.Build, jobId, "succeeded", outputs);
        await WaitForJobAsync(jobId, j => j.State == JobState.Succeeded);
        var build = (await ReadAsync<Page<Build>>(await Http.GetAsync($"/api/assets/{cart.Id}/builds"))).Items.Single();
        return (pack, build);
    }

    private static async Task SetPaletteAsync(Guid packId, byte[] main, params string[] variants)
    {
        var mainId = await UploadAsync(main, "palette.png");
        await using var scope = Services.CreateAsyncScope();
        var db = scope.ServiceProvider.GetRequiredService<SlopolyDb>();
        (await db.Packs.FindAsync(packId))!.PaletteTextureFileId = mainId;
        foreach (var name in variants)
            db.PaletteVariants.Add(new PaletteVariant { PackId = packId, Name = name, TextureFileId = await UploadAsync([9], $"palette_{name}.png") });
        await db.SaveChangesAsync();
    }

    private static async Task<Dictionary<string, byte[]>> EntriesAsync(Guid buildId)
    {
        var response = await Http.GetAsync($"/api/builds/{buildId}/blend");
        Assert.That(response.IsSuccessStatusCode, await response.Content.ReadAsStringAsync());
        using var zip = new ZipArchive(await response.Content.ReadAsStreamAsync());
        var entries = new Dictionary<string, byte[]>();
        foreach (var entry in zip.Entries)
        {
            using var stream = new MemoryStream();
            await entry.Open().CopyToAsync(stream);
            entries[entry.FullName] = stream.ToArray();
        }
        return entries;
    }

    [Test]
    public async Task ZipHasTheBlendFileAndTheCurrentPaletteTextures()
    {
        var (pack, build) = await BuildAsync(withBlend: true);
        await SetPaletteAsync(pack.Id, [1, 1, 1], "autumn");
        var entries = await EntriesAsync(build.Id);
        Assert.That(entries.Keys.Order(StringComparer.Ordinal), Is.EqualTo(new[] { "palette.png", "palette_autumn.png", "wooden_cart.blend" }));
        Assert.That(entries["palette.png"], Is.EqualTo(new byte[] { 1, 1, 1 }));

        // A palette edit after the build: the download carries the new texture without a rebuild.
        await SetPaletteAsync(pack.Id, [2, 2, 2]);
        Assert.That((await EntriesAsync(build.Id))["palette.png"], Is.EqualTo(new byte[] { 2, 2, 2 }));
    }

    [Test]
    public async Task BuildWithoutBlendFileAsksForARebuild()
    {
        var (_, build) = await BuildAsync(withBlend: false);
        var response = await Http.GetAsync($"/api/builds/{build.Id}/blend");
        Assert.That(response.StatusCode, Is.EqualTo(HttpStatusCode.Conflict));
        Assert.That(await response.Content.ReadAsStringAsync(), Does.Contain("rebuild"));
    }
}
