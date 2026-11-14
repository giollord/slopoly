using System.Net;
using System.Net.Http.Json;
using System.Text.Json.Nodes;
using Slopoly.Contracts;
using static Slopoly.Tests.Api.ApiFixture;

namespace Slopoly.Tests.Api;

/// <summary>surface-shading: pack shading settings (tasks 3.1–3.3).</summary>
public sealed class ShadingTests
{
    [Test]
    public async Task NewPacksAreFlatAndEditsPersist()
    {
        var pack = await CreatePackAsync();
        Assert.That((pack.ShadingMode, pack.HardEdgeAngle, pack.ShadeStrength), Is.EqualTo((ShadingMode.Flat, 60.0, 0.5)));

        var client = Client();
        await ReadAsync<Pack>(await client.PatchAsJsonAsync($"/api/packs/{pack.Id}",
            new PackEdit(null, null, null, null, ShadingMode.Smooth, 30, 0.2), Json));
        var read = await ReadAsync<Pack>(await client.GetAsync($"/api/packs/{pack.Id}"));
        Assert.That((read.ShadingMode, read.HardEdgeAngle, read.ShadeStrength, read.StyleText),
            Is.EqualTo((ShadingMode.Smooth, 30.0, 0.2, pack.StyleText)));
    }

    [TestCase(-1.0, null)]
    [TestCase(181.0, null)]
    [TestCase(null, 1.5)]
    [TestCase(null, -0.1)]
    public async Task OutOfRangeValuesAreRefused(double? angle, double? strength)
    {
        var pack = await CreatePackAsync();
        var response = await Client().PatchAsJsonAsync($"/api/packs/{pack.Id}", new PackEdit(null, null, null, null, null, angle, strength), Json);
        Assert.That(response.StatusCode, Is.EqualTo(HttpStatusCode.BadRequest));
    }

    [Test]
    public async Task BuildInputsCarryThePacksShading()
    {
        var pack = await CreatePackAsync();
        var client = Client();
        await ReadAsync<Pack>(await client.PatchAsJsonAsync($"/api/packs/{pack.Id}", new PackEdit(null, null, null, null, ShadingMode.Smooth, 35, 0.7), Json));
        var asset = await ReadAsync<Asset>(await client.PostAsJsonAsync($"/api/packs/{pack.Id}/assets", new AssetCreate("crate", ""), Json));
        var submitted = await ReadAsync<JsonObject>(await client.PostAsJsonAsync($"/api/assets/{asset.Id}/programs", new ProgramSubmit("part('crate', box(1, 1, 1))", null), Json));
        var message = await TakeJobAsync(JobKinds.Build, submitted["job"]!["id"]!.GetValue<Guid>());
        var shading = message.Inputs["shading"]!;
        Assert.That((shading["mode"]!.GetValue<string>(), shading["hardEdgeAngle"]!.GetValue<double>(), shading["shadeStrength"]!.GetValue<double>()),
            Is.EqualTo(("smooth", 35.0, 0.7)));
    }

    [Test]
    public async Task UpdateStyleChangesShadingThroughMcp()
    {
        var pack = await CreatePackAsync();
        await using var client = await McpToolsTests.ConnectAsync();
        var updated = await McpToolsTests.CallAsync(client, "update_style", new()
        {
            ["packId"] = pack.Id, ["shadingMode"] = "Smooth", ["shadeStrength"] = 0.0,
        });
        Assert.That((updated.GetProperty("shadingMode").GetString(), updated.GetProperty("shadeStrength").GetDouble()), Is.EqualTo(("Smooth", 0.0)));
        var overview = await McpToolsTests.CallAsync(client, "get_pack", new() { ["packId"] = pack.Id });
        Assert.That(overview.GetProperty("pack").GetProperty("hardEdgeAngle").GetDouble(), Is.EqualTo(60.0));
    }
}
