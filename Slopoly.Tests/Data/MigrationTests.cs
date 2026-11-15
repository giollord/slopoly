using Microsoft.Data.Sqlite;
using Microsoft.EntityFrameworkCore;
using Microsoft.EntityFrameworkCore.Infrastructure;
using Microsoft.EntityFrameworkCore.Migrations;
using Slopoly.ApiService.Data;
using Slopoly.Contracts;

namespace Slopoly.Tests.Data;

/// <summary>Upgrading data made before variants and chats existed (task 1.2).</summary>
public sealed class MigrationTests
{
    private const string Before = "20261114230220_PackShading";

    /// <summary>Replaces @T1..@T9 by stored timestamps (UTC binary, as the DateTimeOffset converter writes them).</summary>
    private static string Times(string sql)
    {
        var converter = new Microsoft.EntityFrameworkCore.Storage.ValueConversion.DateTimeOffsetToBinaryConverter();
        for (var i = 1; i <= 9; i++)
            sql = sql.Replace($"@T{i}", converter.ConvertToProvider(DateTimeOffset.UnixEpoch.AddMinutes(i))!.ToString());
        return sql;
    }

    [Test]
    public async Task ExistingRowsMoveIntoDefaultVariantAndPackChat()
    {
        var path = Path.Combine(Path.GetTempPath(), $"slopoly-migration-{Guid.NewGuid():N}.db");
        try
        {
            var options = new DbContextOptionsBuilder<SlopolyDb>().UseSqlite($"Data Source={path};Pooling=False").Options;
            await using (var db = new SlopolyDb(options))
            {
                await db.GetService<IMigrator>().MigrateAsync(Before);
                await db.Database.ExecuteSqlRawAsync(Times("""
                    INSERT INTO Packs (Id, AgentSessionId, CreatedAt, HardEdgeAngle, Instructions, Name, PolyBudget, ShadeStrength, ShadingMode, StyleText)
                        VALUES ('00000000-0000-0000-0000-0000000000A1', 'session-1', @T1, 60, '', 'Village', 2000, 0.5, 'Flat', '');
                    INSERT INTO Assets (Id, CreatedAt, CurrentProgramVersionId, Description, Name, PackId, Status)
                        VALUES ('00000000-0000-0000-0000-0000000000B1', @T1, '00000000-0000-0000-0000-0000000000C2', 'a cart', 'cart', '00000000-0000-0000-0000-0000000000A1', 'Built');
                    INSERT INTO ProgramVersions (Id, AssetId, CreatedAt, Note, Number, Source) VALUES
                        ('00000000-0000-0000-0000-0000000000C1', '00000000-0000-0000-0000-0000000000B1', @T1, '', 1, 'a'),
                        ('00000000-0000-0000-0000-0000000000C2', '00000000-0000-0000-0000-0000000000B1', @T2, '', 2, 'b');
                    INSERT INTO Builds (Id, AssetId, CreatedAt, JobId, PaletteEntryIds, ProgramVersionId, Validated)
                        VALUES ('00000000-0000-0000-0000-0000000000D1', '00000000-0000-0000-0000-0000000000B1', @T3, '00000000-0000-0000-0000-0000000000E9', '[]', '00000000-0000-0000-0000-0000000000C2', 0);
                    INSERT INTO Manifests (AssetId, Content, UpdatedAt) VALUES ('00000000-0000-0000-0000-0000000000B1', '{{"parts":[]}}', @T1);
                    INSERT INTO ConceptImages (Id, AssetId, CreatedAt, FileId, Height, Kind, PackId, Selection, Width, SourceConceptId, View) VALUES
                        ('00000000-0000-0000-0000-0000000000F1', '00000000-0000-0000-0000-0000000000B1', @T1, '00000000-0000-0000-0000-000000000001', 1, 'Hero', '00000000-0000-0000-0000-0000000000A1', 'Picked', 1, NULL, NULL),
                        ('00000000-0000-0000-0000-0000000000F2', '00000000-0000-0000-0000-0000000000B1', @T1, '00000000-0000-0000-0000-000000000002', 1, 'View', '00000000-0000-0000-0000-0000000000A1', 'None', 1, '00000000-0000-0000-0000-0000000000F1', 'front'),
                        ('00000000-0000-0000-0000-0000000000F3', NULL, @T1, '00000000-0000-0000-0000-000000000003', 1, 'Anchor', '00000000-0000-0000-0000-0000000000A1', 'Picked', 1, NULL, NULL);
                    INSERT INTO Scenes (Id, Description, Name, PackId, Placements, UpdatedAt)
                        VALUES ('00000000-0000-0000-0000-0000000000AA', '', 'square', '00000000-0000-0000-0000-0000000000A1', '[]', @T1);
                    INSERT INTO Jobs (Id, Attempt, CreatedAt, Inputs, Kind, PackId, State) VALUES
                        ('00000000-0000-0000-0000-0000000000E1', 1, @T5, '{{}}', 'agent-turn', '00000000-0000-0000-0000-0000000000A1', 'Succeeded'),
                        ('00000000-0000-0000-0000-0000000000E2', 1, @T6, '{{}}', 'agent-turn', '00000000-0000-0000-0000-0000000000A1', 'Succeeded'),
                        ('00000000-0000-0000-0000-0000000000E3', 1, @T7, '{{}}', 'agent-turn', '00000000-0000-0000-0000-0000000000A1', 'Failed'),
                        ('00000000-0000-0000-0000-0000000000E9', 1, @T2, '{{}}', 'build', '00000000-0000-0000-0000-0000000000A1', 'Succeeded');
                    """));
                await db.Database.MigrateAsync();
            }

            await using (var db = new SlopolyDb(options))
            {
                var assetId = Guid.Parse("00000000-0000-0000-0000-0000000000B1");
                var packId = Guid.Parse("00000000-0000-0000-0000-0000000000A1");
                var asset = await db.Assets.SingleAsync();
                var variant = await db.AssetVariants.SingleAsync();
                Assert.That(variant.Id, Is.EqualTo(assetId));
                Assert.That(variant.Name, Is.EqualTo("default"));
                Assert.That(variant.Status, Is.EqualTo(AssetStatus.Built));
                Assert.That(variant.CurrentProgramVersionId, Is.EqualTo(Guid.Parse("00000000-0000-0000-0000-0000000000C2")));
                Assert.That(asset.DefaultVariantId, Is.EqualTo(variant.Id));
                Assert.That(await db.ProgramVersions.AllAsync(v => v.VariantId == variant.Id), Is.True);
                Assert.That(await db.ProgramVersions.CountAsync(), Is.EqualTo(2));
                Assert.That((await db.Builds.SingleAsync()).VariantId, Is.EqualTo(variant.Id));
                Assert.That((await db.Manifests.SingleAsync()).VariantId, Is.EqualTo(variant.Id));
                var concepts = await db.ConceptImages.ToDictionaryAsync(c => c.Kind);
                Assert.That(concepts[ConceptKind.Hero].VariantId, Is.EqualTo(variant.Id));
                Assert.That(concepts[ConceptKind.View].VariantId, Is.EqualTo(variant.Id));
                Assert.That(concepts[ConceptKind.Anchor].VariantId, Is.Null);
                Assert.That((await db.Scenes.SingleAsync()).Versions, Is.Empty);

                var chat = await db.Chats.SingleAsync();
                Assert.That(chat.Id, Is.EqualTo(packId));
                Assert.That(chat.PackId, Is.EqualTo(packId));
                Assert.That(chat.SessionId, Is.EqualTo("session-1"));
                Assert.That(chat.Context, Is.EqualTo(new ChatContext(ChatPages.Pack, packId)));
                Assert.That(await db.Jobs.CountAsync(j => j.ChatId == chat.Id), Is.EqualTo(3));
                Assert.That(await db.Jobs.CountAsync(j => j.ChatId == null), Is.EqualTo(1));
            }
        }
        finally
        {
            SqliteConnection.ClearAllPools();
            File.Delete(path);
        }
    }
}
