using System.Net.Http.Json;
using System.Text.Json.Nodes;
using Slopoly.Contracts;
using static Slopoly.Tests.Api.ApiFixture;

namespace Slopoly.Tests.Api;

/// <summary>surface-shading: the build report's shading defects reach the agent (task 8.3; the geometry tests check
/// how the worker finds them).</summary>
public sealed class ShadingReportTests
{
    [Test]
    public async Task BuildReportToolReturnsTheShadingSection()
    {
        var pack = await CreatePackAsync();
        var leaf = await ReadAsync<Asset>(await Client().PostAsJsonAsync($"/api/packs/{pack.Id}/assets", new AssetCreate("leaf", ""), Json));
        var submitted = await ReadAsync<JsonObject>(await Client().PostAsJsonAsync($"/api/assets/{leaf.Id}/programs",
            new ProgramSubmit("part('leaf', ngon(4, r=0.5, tag='leaf'))", null), Json));
        var jobId = submitted["job"]!["id"]!.GetValue<Guid>();
        await TakeJobAsync(JobKinds.Build, jobId);
        var shading = new JsonObject
        {
            ["merged"] = 0, ["removed"] = 0, ["flipped"] = 0,
            ["parts"] = new JsonArray(new JsonObject { ["part"] = "leaf", ["openEdges"] = 4, ["inward"] = 0, ["bent"] = 0 }),
        };
        await PublishEventAsync(JobKinds.Build, jobId, "succeeded", new JsonObject
        {
            ["glbFileId"] = await UploadAsync([1], "m.glb"), ["validated"] = true, ["report"] = new JsonObject { ["shading"] = shading },
            ["paletteEntryIds"] = new JsonArray(),
        });
        await WaitForJobAsync(jobId, j => j.State == JobState.Succeeded);

        await using var client = await McpToolsTests.ConnectAsync();
        var report = await McpToolsTests.CallAsync(client, "get_build_report", new() { ["assetId"] = leaf.Id });
        var part = report.GetProperty("report").GetProperty("shading").GetProperty("parts")[0];
        Assert.That((part.GetProperty("part").GetString(), part.GetProperty("openEdges").GetInt32()), Is.EqualTo(("leaf", 4)));
    }
}
