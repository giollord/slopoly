using System.Net;
using System.Text.Json;
using System.Text.Json.Nodes;
using System.Text.RegularExpressions;
using Microsoft.AspNetCore.SignalR.Client;
using Microsoft.Extensions.DependencyInjection;
using ModelContextProtocol.Client;
using ModelContextProtocol.Protocol;
using Slopoly.ApiService.Data;
using Slopoly.Contracts;
using static Slopoly.Tests.Api.ApiFixture;

namespace Slopoly.Tests.Api;

/// <summary>design-agent tool surface (tasks 8.1, 8.2).</summary>
public sealed partial class McpToolsTests
{
    internal static async Task<McpClient> ConnectAsync()
    {
        var http = WorkerClient();
        var transport = new HttpClientTransport(new HttpClientTransportOptions { Endpoint = new Uri(http.BaseAddress!, "/mcp") }, http);
        return await McpClient.CreateAsync(transport);
    }

    internal static async Task<JsonElement> CallAsync(McpClient client, string tool, Dictionary<string, object?> args)
    {
        var result = await client.CallToolAsync(tool, args);
        var text = result.Content.OfType<TextContentBlock>().Single().Text;
        Assert.That(result.IsError, Is.Not.True, text);
        return JsonDocument.Parse(text).RootElement;
    }

    [Test]
    public async Task ToolsAreListedAndCreateAssetReachesTheUi()
    {
        await using var client = await ConnectAsync();
        var tools = (await client.ListToolsAsync()).Select(t => t.Name).Order().ToList();
        Assert.That(tools, Is.EqualTo(new[]
        {
            "cancel_job", "create_asset", "get_build_report", "get_job", "get_pack", "get_palette", "get_part_colors",
            "get_scene", "get_segmentation", "list_concepts", "read_knowledge", "retry_job", "revise_concept", "save_manifest",
            "save_scene", "search_knowledge", "start_job", "submit_program", "update_asset", "update_style",
            "upsert_palette_entries", "upsert_palette_variant", "view_image", "write_knowledge",
        }));

        var pack = await CreatePackAsync();
        await using var hub = await HubAsync();
        var announced = new TaskCompletionSource<ChangeEvent>();
        hub.On<ChangeEvent>(Realtime.Changed, e => { if (e.Entity == nameof(Asset)) announced.TrySetResult(e); });
        var asset = await CallAsync(client, "create_asset", new() { ["packId"] = pack.Id, ["name"] = "wooden cart", ["description"] = "a small cart" });
        var change = await announced.Task.WaitAsync(TimeSpan.FromSeconds(5));
        Assert.That(change.Id, Is.EqualTo(asset.GetProperty("id").GetGuid()));
        Assert.That(change.PackId, Is.EqualTo(pack.Id));
    }

    [Test]
    public async Task McpNeedsTheWorkerKey()
    {
        var response = await Client().PostAsync("/mcp", new StringContent("{}"));
        Assert.That(response.StatusCode, Is.EqualTo(HttpStatusCode.Unauthorized));
    }

    [Test]
    public async Task ServiceErrorsComeBackAsToolErrors()
    {
        await using var client = await ConnectAsync();
        var result = await client.CallToolAsync("get_job", new Dictionary<string, object?> { ["jobId"] = Guid.NewGuid() });
        Assert.That(result.IsError, Is.True);
        Assert.That(result.Content.OfType<TextContentBlock>().Single().Text, Is.EqualTo("Job not found."));
    }

    [GeneratedRegex("[A-Za-z0-9+/]{120,}={0,2}")]
    private static partial Regex Base64Run();

    [Test]
    public async Task ResultsCarryIdsAndNumbersAndOnlyViewImageReturnsImages()
    {
        var pack = await CreatePackAsync();
        var image = await UploadAsync([.. Enumerable.Range(0, 3000).Select(i => (byte)i)], "view.png");
        Guid assetId, conceptId;
        await using (var scope = Services.CreateAsyncScope())
        {
            var db = scope.ServiceProvider.GetRequiredService<SlopolyDb>();
            var asset = new Asset { PackId = pack.Id, Name = "cart" };
            var hero = new ConceptImage { PackId = pack.Id, AssetId = asset.Id, FileId = image, Kind = ConceptKind.Hero,
                Selection = Selection.Picked, Width = 1024, Height = 1024, FrontYaw = 175, Front = "detected" };
            var concept = new ConceptImage { PackId = pack.Id, AssetId = asset.Id, FileId = image, Kind = ConceptKind.View, View = "front",
                SourceConceptId = hero.Id, MaskFileId = image, Width = 768, Height = 768 };
            var version = new ProgramVersion { AssetId = asset.Id, Number = 1, Source = "part('bed', box(1, 1, 1))" };
            db.AddRange(asset, hero, concept, version,
                new PartMask { ConceptImageId = concept.Id, Part = "wheel", View = "front", FileId = image, Bounds = new(10, 300, 80, 200), Area = 9000,
                    Colors = [new MeasuredColor("#6e4524", 0.8)] },
                new Build { AssetId = asset.Id, ProgramVersionId = version.Id, GlbFileId = image, Validated = true,
                    Report = JsonNode.Parse($$"""{ "silhouette": { "views": [ { "view": "front", "compareFileId": "{{image}}", "renderFileId": "{{image}}", "parts": [ { "mask": "wheel", "iou": 0.81, "width_error": -0.04 } ] } ] } }""")!.AsObject() });
            await db.SaveChangesAsync();
            (assetId, conceptId) = (asset.Id, concept.Id);
        }

        await using var client = await ConnectAsync();
        foreach (var (tool, args) in new (string, Dictionary<string, object?>)[]
                 {
                     ("get_segmentation", new() { ["conceptImageId"] = conceptId }),
                     ("get_part_colors", new() { ["conceptImageId"] = conceptId }),
                     ("get_build_report", new() { ["assetId"] = assetId }),
                 })
        {
            var result = await client.CallToolAsync(tool, args);
            Assert.That(result.Content, Has.All.InstanceOf<TextContentBlock>(), tool);
            Assert.That(Base64Run().IsMatch(JsonSerializer.Serialize(result)), Is.False, $"{tool} returned an encoded payload");
        }
        var report = await CallAsync(client, "get_build_report", new() { ["assetId"] = assetId });
        var scored = report.GetProperty("report").GetProperty("silhouette").GetProperty("views")[0];
        Assert.That(scored.GetProperty("parts")[0].GetProperty("width_error").GetDouble(), Is.EqualTo(-0.04));
        Assert.That(scored.GetProperty("compareFileId").GetGuid(), Is.EqualTo(image)); // an id to pass to view_image, not image data
        var segmentation = await CallAsync(client, "get_segmentation", new() { ["conceptImageId"] = conceptId });
        var front = segmentation.GetProperty("views")[0];
        Assert.That(front.GetProperty("masks")[0].GetProperty("fileId").GetGuid(), Is.EqualTo(image));
        Assert.That((front.GetProperty("view").GetString(), segmentation.GetProperty("frontYaw").GetDouble()), Is.EqualTo(("front", 175.0)));

        var view = await client.CallToolAsync("view_image", new Dictionary<string, object?> { ["fileId"] = image });
        var block = view.Content.OfType<ImageContentBlock>().Single();
        Assert.That(block.MimeType, Is.EqualTo("image/png"));
    }
}
