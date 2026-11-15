using System.Net.Http.Json;
using System.Text.Json.Nodes;
using Slopoly.Contracts;
using static Slopoly.Tests.Api.ApiFixture;

namespace Slopoly.Tests.Api;

/// <summary>design-agent chats: list, turns, page context and stop (tasks 5.1, 5.2, 5.4).</summary>
public sealed class ChatTests
{
    private static HttpClient Http => Client();

    private static async Task<Chat> NewChatAsync(ChatContext context) =>
        await ReadAsync<Chat>(await Http.PostAsJsonAsync("/api/chats", new ChatCreate(context), Json));

    private static async Task<Job> SendAsync(Guid chatId, string message, ChatContext? context = null) =>
        await ReadAsync<Job>(await Http.PostAsJsonAsync($"/api/chats/{chatId}/messages", new ChatMessage(message, context), Json));

    private static async Task<string> PromptAsync(Job job) => (await TakeJobAsync(JobKinds.AgentTurn, job.Id)).Inputs["prompt"]!.GetValue<string>();

    [Test]
    public async Task ChatsListNewestFirstAndTurnsPageFromTheEnd()
    {
        var pack = await CreatePackAsync();
        var older = await NewChatAsync(new ChatContext(ChatPages.Pack, pack.Id));
        await SendAsync(older.Id, "first chat");
        var chat = await NewChatAsync(new ChatContext(ChatPages.Pack, pack.Id));
        var jobs = new List<Job>();
        for (var i = 0; i < 3; i++) jobs.Add(await SendAsync(chat.Id, $"message {i}"));

        var chats = await ReadAsync<Page<Chat>>(await Http.GetAsync($"/api/chats?packId={pack.Id}"));
        Assert.That(chats.Items.Select(c => c.Id), Is.EqualTo(new[] { chat.Id, older.Id }));
        Assert.That(chats.Items[0].Title, Is.EqualTo("message 0"));

        var last = await ReadAsync<Page<ChatTurn>>(await Http.GetAsync($"/api/chats/{chat.Id}/turns?take=2"));
        Assert.That(last.Total, Is.EqualTo(3));
        Assert.That(last.Items.Select(t => t.Job.Inputs["message"]!.GetValue<string>()), Is.EqualTo(new[] { "message 1", "message 2" }));
        var earlier = await ReadAsync<Page<ChatTurn>>(await Http.GetAsync($"/api/chats/{chat.Id}/turns?take=2&before={last.Items[0].Job.Id}"));
        Assert.That(earlier.Items.Select(t => t.Job.Inputs["message"]!.GetValue<string>()), Is.EqualTo(new[] { "message 0" }));
        Assert.That(jobs, Has.All.Matches<Job>(j => j.ChatId == chat.Id));
    }

    [Test]
    public async Task FirstMessageCarriesTheAssetContextAndLaterOnesTheViewingLine()
    {
        var pack = await CreatePackAsync();
        var cart = await ReadAsync<Asset>(await Http.PostAsJsonAsync($"/api/packs/{pack.Id}/assets", new AssetCreate("cart", "a hand cart"), Json));
        var loaded = await ReadAsync<AssetVariant>(await Http.PostAsJsonAsync($"/api/assets/{cart.Id}/variants", new VariantCreate("loaded"), Json));
        var submitted = await ReadAsync<JsonObject>(await Http.PostAsJsonAsync($"/api/assets/{cart.Id}/programs?variantId={loaded.Id}",
            new ProgramSubmit("part('a', box(1, 1, 1))", null), Json));
        var buildJob = submitted["job"]!["id"]!.GetValue<Guid>();
        await TakeJobAsync(JobKinds.Build, buildJob);
        await PublishEventAsync(JobKinds.Build, buildJob, "succeeded", new JsonObject
        {
            ["glbFileId"] = await UploadAsync([1], "m.glb"), ["validated"] = false, ["report"] = new JsonObject(), ["paletteEntryIds"] = new JsonArray(),
        });
        await WaitForJobAsync(buildJob, j => j.State == JobState.Succeeded);
        var build = (await ReadAsync<Page<Build>>(await Http.GetAsync($"/api/assets/{cart.Id}/builds?variantId={loaded.Id}"))).Items.Single();

        var context = new ChatContext(ChatPages.Asset, pack.Id, cart.Id, loaded.Id, build.Id);
        var chat = await NewChatAsync(context);
        Assert.That((chat.PackId, chat.AssetId, chat.VariantId), Is.EqualTo(((Guid?)pack.Id, (Guid?)cart.Id, (Guid?)loaded.Id)));
        var first = await PromptAsync(await SendAsync(chat.Id, "the wheels are too thick", context));
        Assert.That(first, Does.StartWith("[Context]\nThe user is on the asset page."));
        Assert.That(first, Does.Contain($"Pack \"Test pack\" (id {pack.Id})"));
        Assert.That(first, Does.Contain($"Asset \"cart\" (id {cart.Id})"));
        Assert.That(first, Does.Contain($"Variant \"loaded\" (id {loaded.Id})"));
        Assert.That(first, Does.Contain($"Selected build (id {build.Id}): program v1"));
        Assert.That(first, Does.EndWith("[/Context]\n\nthe wheels are too thick"));

        var well = await ReadAsync<Asset>(await Http.PostAsJsonAsync($"/api/packs/{pack.Id}/assets", new AssetCreate("well", ""), Json));
        var later = await PromptAsync(await SendAsync(chat.Id, "and this one?", new ChatContext(ChatPages.Asset, pack.Id, well.Id)));
        Assert.That(later, Does.StartWith($"[Viewing: asset page · pack \"Test pack\" ({pack.Id}) · asset \"well\" ({well.Id}) · variant \"default\" ({well.DefaultVariantId})]\n"));
        Assert.That(later, Does.EndWith("and this one?"));
    }

    [Test]
    public async Task ChatOutsideAPackSaysWhereTheUserIs()
    {
        var chat = await NewChatAsync(new ChatContext(ChatPages.Knowledge));
        Assert.That(chat.PackId, Is.Null);
        var job = await SendAsync(chat.Id, "what techniques exist?");
        Assert.That(job.PackId, Is.Null);
        var prompt = await PromptAsync(job);
        Assert.That(prompt, Does.StartWith("[Context]\nThe user is on the knowledge page.\n[/Context]"));
    }

    [Test]
    public async Task ConceptContextIsRecorded()
    {
        var pack = await CreatePackAsync();
        var concept = Guid.NewGuid();
        var chat = await NewChatAsync(new ChatContext(ChatPages.Concept, pack.Id, ConceptId: concept));
        var stored = await ReadAsync<Chat>(await Http.GetAsync($"/api/chats/{chat.Id}"));
        Assert.That(stored.Context, Is.EqualTo(new ChatContext(ChatPages.Concept, pack.Id, ConceptId: concept)));
    }

    [Test]
    public async Task StoppedTurnKeepsTheSessionForTheNextMessage()
    {
        var pack = await CreatePackAsync();
        var chat = await NewChatAsync(new ChatContext(ChatPages.Pack, pack.Id));
        var running = await SendAsync(chat.Id, "model the cart");
        var queued = await SendAsync(chat.Id, "then the well");
        await TakeJobAsync(JobKinds.AgentTurn, running.Id);
        await PublishEventAsync(JobKinds.AgentTurn, running.Id, "started");
        await PublishEventAsync(JobKinds.AgentTurn, running.Id, "stream", data: new JsonObject { ["kind"] = "session", ["sessionId"] = "s-42" });
        await WaitForAsync(async () => (await ReadAsync<Chat>(await Http.GetAsync($"/api/chats/{chat.Id}"))).SessionId == "s-42");

        var stopped = await ReadAsync<List<Job>>(await Http.PostAsync($"/api/chats/{chat.Id}/stop", null));
        Assert.That(stopped.Select(j => j.Id), Is.EquivalentTo(new[] { running.Id, queued.Id }));
        Assert.That((await ReadAsync<Job>(await Http.GetAsync($"/api/jobs/{running.Id}"))).State, Is.EqualTo(JobState.Cancelled));
        Assert.That((await ReadAsync<Job>(await Http.GetAsync($"/api/jobs/{queued.Id}"))).State, Is.EqualTo(JobState.Cancelled));

        var next = await SendAsync(chat.Id, "only fix the handles");
        var message = await TakeJobAsync(JobKinds.AgentTurn, next.Id);
        Assert.That(message.Inputs["sessionId"]!.GetValue<string>(), Is.EqualTo("s-42"));
        Assert.That(message.Inputs["prompt"]!.GetValue<string>(), Does.StartWith("[Viewing:"));
    }

    private static async Task WaitForAsync(Func<Task<bool>> condition)
    {
        var deadline = DateTime.UtcNow + TimeSpan.FromSeconds(10);
        while (DateTime.UtcNow < deadline)
        {
            if (await condition()) return;
            await Task.Delay(50);
        }
        Assert.Fail("Condition not met in time.");
    }
}
