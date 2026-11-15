using Slopoly.ApiService.Data;
using Slopoly.Contracts;
using static Slopoly.Tests.Api.ApiFixture;

namespace Slopoly.Tests.Api;

/// <summary>Paged history lists (task 4.1).</summary>
public sealed class PagingTests
{
    [Test]
    public async Task JobsArePagedNewestFirstWithTheTotal()
    {
        var pack = await CreatePackAsync();
        await using (var scope = Services.CreateAsyncScope())
        {
            var db = scope.ServiceProvider.GetRequiredService<SlopolyDb>();
            var start = DateTimeOffset.UtcNow.AddHours(-1);
            db.Jobs.AddRange(Enumerable.Range(0, 60).Select(i => new Job
            {
                Kind = JobKinds.Comfy, Operation = $"op {i}", PackId = pack.Id, State = JobState.Succeeded, CreatedAt = start.AddSeconds(i),
            }));
            await db.SaveChangesAsync();
        }

        var first = await ReadAsync<Page<Job>>(await Client().GetAsync($"/api/packs/{pack.Id}/jobs"));
        Assert.That(first.Total, Is.EqualTo(60));
        Assert.That(first.Items.Select(j => j.Operation), Is.EqualTo(Enumerable.Range(35, 25).Reverse().Select(i => $"op {i}")));

        var second = await ReadAsync<Page<Job>>(await Client().GetAsync($"/api/packs/{pack.Id}/jobs?skip=25&take=25"));
        Assert.That(second.Items.Select(j => j.Operation), Is.EqualTo(Enumerable.Range(10, 25).Reverse().Select(i => $"op {i}")));

        var capped = await ReadAsync<Page<Job>>(await Client().GetAsync($"/api/packs/{pack.Id}/jobs?take=1000"));
        Assert.That(capped.Items, Has.Count.EqualTo(60));
    }
}
