using System.Net.Http.Json;
using System.Text.Json.Nodes;
using Microsoft.EntityFrameworkCore;
using Slopoly.ApiService.Data;
using Slopoly.Contracts;
using static Slopoly.Tests.Api.ApiFixture;

namespace Slopoly.Tests.Api;

/// <summary>asset-packs: pack deletion (task 9.1).</summary>
public sealed class PackDeletionTests
{
    private static HttpClient Http => Client();

    [Test]
    public async Task DeletingAPackCancelsItsJobsAndRemovesEverythingButKnowledge()
    {
        var pack = await CreatePackAsync("Doomed");
        var cart = await ReadAsync<Asset>(await Http.PostAsJsonAsync($"/api/packs/{pack.Id}/assets", new AssetCreate("cart", ""), Json));
        await ReadAsync<AssetVariant>(await Http.PostAsJsonAsync($"/api/assets/{cart.Id}/variants", new VariantCreate("loaded"), Json));
        await Http.PutAsJsonAsync($"/api/assets/{cart.Id}/manifest", JsonNode.Parse("""{ "parts": [ { "name": "bed" } ] }"""));
        var submitted = await ReadAsync<JsonObject>(await Http.PostAsJsonAsync($"/api/assets/{cart.Id}/programs", new ProgramSubmit("part('a', box(1, 1, 1))", null), Json));
        var buildJob = submitted["job"]!["id"]!.GetValue<Guid>();
        await TakeJobAsync(JobKinds.Build, buildJob);
        await PublishEventAsync(JobKinds.Build, buildJob, "succeeded", new JsonObject
        {
            ["glbFileId"] = await UploadAsync([1], "m.glb"), ["validated"] = true, ["report"] = new JsonObject(), ["paletteEntryIds"] = new JsonArray(),
        });
        await WaitForJobAsync(buildJob, j => j.State == JobState.Succeeded);
        await ReadAsync<Scene>(await Http.PutAsJsonAsync($"/api/packs/{pack.Id}/scenes", new SceneEdit("square", null, [new("cart 1", cart.Id, [0, 0, 0])]), Json));
        await Http.PutAsJsonAsync($"/api/packs/{pack.Id}/palette/entries", new List<PaletteEntryEdit> { new("wood", null, "#a0703c", null) }, Json);
        await Http.PutAsJsonAsync($"/api/packs/{pack.Id}/palette/variants", new VariantEdit("autumn", [new VariantColorEdit("wood", "#ff0000", null)]), Json);
        using (var form = new MultipartFormDataContent { { new ByteArrayContent([9]), "file", "ref.png" } })
            await ReadAsync<StyleReference>(await Http.PostAsync($"/api/packs/{pack.Id}/style-references", form));
        var running = await SendChatAsync(pack.Id, "keep modelling");
        await TakeJobAsync(JobKinds.AgentTurn, running.Id);
        await PublishEventAsync(JobKinds.AgentTurn, running.Id, "started");
        await WaitForJobAsync(running.Id, j => j.State == JobState.Running);
        var note = new KnowledgeNote("techniques/deletion-test", "Deletion test", ["test"], "stays", "body");
        await ReadAsync<KnowledgeNote>(await Http.PutAsJsonAsync($"/api/knowledge/{note.Slug}", note, Json));

        var deleted = await Http.DeleteAsync($"/api/packs/{pack.Id}");
        Assert.That(deleted.IsSuccessStatusCode, await deleted.Content.ReadAsStringAsync());

        Assert.That((await Http.GetAsync($"/api/packs/{pack.Id}")).StatusCode, Is.EqualTo(HttpStatusCode.NotFound));
        Assert.That((await Http.GetAsync($"/api/jobs/{running.Id}")).StatusCode, Is.EqualTo(HttpStatusCode.NotFound));
        await using (var scope = Services.CreateAsyncScope())
        {
            var db = scope.ServiceProvider.GetRequiredService<SlopolyDb>();
            Assert.That(await db.Assets.AnyAsync(a => a.PackId == pack.Id), Is.False);
            Assert.That(await db.AssetVariants.AnyAsync(v => v.AssetId == cart.Id), Is.False);
            Assert.That(await db.ProgramVersions.AnyAsync(v => v.AssetId == cart.Id), Is.False);
            Assert.That(await db.Builds.AnyAsync(b => b.AssetId == cart.Id), Is.False);
            Assert.That(await db.Manifests.AnyAsync(m => m.AssetId == cart.Id), Is.False);
            Assert.That(await db.Scenes.AnyAsync(s => s.PackId == pack.Id), Is.False);
            Assert.That(await db.PaletteEntries.AnyAsync(e => e.PackId == pack.Id), Is.False);
            Assert.That(await db.PaletteVariants.AnyAsync(v => v.PackId == pack.Id), Is.False);
            Assert.That(await db.StyleReferences.AnyAsync(r => r.PackId == pack.Id), Is.False);
            Assert.That(await db.Jobs.AnyAsync(j => j.PackId == pack.Id), Is.False);
            Assert.That(await db.JobEvents.AnyAsync(e => e.JobId == running.Id), Is.False);
            Assert.That(await db.Chats.AnyAsync(c => c.PackId == pack.Id), Is.False);
        }
        Assert.That((await ReadAsync<KnowledgeNote>(await Http.GetAsync($"/api/knowledge/{note.Slug}"))).Summary, Is.EqualTo("stays"));

        // A late result of the cancelled job is ignored (no job row any more).
        await PublishEventAsync(JobKinds.AgentTurn, running.Id, "succeeded", new JsonObject { ["sessionId"] = "late" });
        await Task.Delay(300);
        Assert.That((await Http.GetAsync($"/api/jobs/{running.Id}")).StatusCode, Is.EqualTo(HttpStatusCode.NotFound));
        await Http.DeleteAsync($"/api/knowledge/{note.Slug}");
    }
}
