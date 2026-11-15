using System;
using Microsoft.EntityFrameworkCore.Migrations;

#nullable disable

namespace Slopoly.ApiService.Data.Migrations;

/// <inheritdoc />
public partial class _20261115001328_VariantsAndChats : Migration
{
    /// <inheritdoc />
    protected override void Up(MigrationBuilder migrationBuilder)
    {
        migrationBuilder.CreateTable(
            name: "AssetVariants",
            columns: table => new
            {
                Id = table.Column<Guid>(type: "TEXT", nullable: false),
                AssetId = table.Column<Guid>(type: "TEXT", nullable: false),
                Name = table.Column<string>(type: "TEXT", nullable: false),
                Status = table.Column<string>(type: "TEXT", nullable: false),
                CurrentProgramVersionId = table.Column<Guid>(type: "TEXT", nullable: true),
                CreatedAt = table.Column<long>(type: "INTEGER", nullable: false)
            },
            constraints: table =>
            {
                table.PrimaryKey("PK_AssetVariants", x => x.Id);
            });

        migrationBuilder.CreateTable(
            name: "Chats",
            columns: table => new
            {
                Id = table.Column<Guid>(type: "TEXT", nullable: false),
                PackId = table.Column<Guid>(type: "TEXT", nullable: true),
                Title = table.Column<string>(type: "TEXT", nullable: false),
                SessionId = table.Column<string>(type: "TEXT", nullable: true),
                Context = table.Column<string>(type: "TEXT", nullable: false),
                AssetId = table.Column<Guid>(type: "TEXT", nullable: true),
                VariantId = table.Column<Guid>(type: "TEXT", nullable: true),
                SceneId = table.Column<Guid>(type: "TEXT", nullable: true),
                CreatedAt = table.Column<long>(type: "INTEGER", nullable: false),
                UpdatedAt = table.Column<long>(type: "INTEGER", nullable: false)
            },
            constraints: table =>
            {
                table.PrimaryKey("PK_Chats", x => x.Id);
            });

        migrationBuilder.AddColumn<string>(
            name: "Versions",
            table: "Scenes",
            type: "TEXT",
            nullable: false,
            defaultValue: "");

        migrationBuilder.AddColumn<Guid>(
            name: "VariantId",
            table: "ProgramVersions",
            type: "TEXT",
            nullable: false,
            defaultValue: new Guid("00000000-0000-0000-0000-000000000000"));

        migrationBuilder.AddColumn<Guid>(
            name: "VariantId",
            table: "Manifests",
            type: "TEXT",
            nullable: false,
            defaultValue: new Guid("00000000-0000-0000-0000-000000000000"));

        migrationBuilder.AddColumn<Guid>(
            name: "ChatId",
            table: "Jobs",
            type: "TEXT",
            nullable: true);

        migrationBuilder.AddColumn<Guid>(
            name: "VariantId",
            table: "ConceptImages",
            type: "TEXT",
            nullable: true);

        migrationBuilder.AddColumn<Guid>(
            name: "BlendFileId",
            table: "Builds",
            type: "TEXT",
            nullable: true);

        migrationBuilder.AddColumn<Guid>(
            name: "VariantId",
            table: "Builds",
            type: "TEXT",
            nullable: false,
            defaultValue: new Guid("00000000-0000-0000-0000-000000000000"));

        migrationBuilder.AddColumn<Guid>(
            name: "DefaultVariantId",
            table: "Assets",
            type: "TEXT",
            nullable: false,
            defaultValue: new Guid("00000000-0000-0000-0000-000000000000"));

        // Backfill before anything is dropped. Each asset's default variant reuses the asset's id, and each pack's
        // first chat reuses the pack's id, so no ids are generated in SQL.
        migrationBuilder.Sql("""
            INSERT INTO AssetVariants (Id, AssetId, Name, Status, CurrentProgramVersionId, CreatedAt)
                SELECT Id, Id, 'default', Status, CurrentProgramVersionId, CreatedAt FROM Assets;
            UPDATE Assets SET DefaultVariantId = Id;
            UPDATE ProgramVersions SET VariantId = AssetId;
            UPDATE Builds SET VariantId = AssetId;
            UPDATE Manifests SET VariantId = AssetId;
            UPDATE ConceptImages SET VariantId = AssetId WHERE AssetId IS NOT NULL AND Kind IN ('Hero', 'View');
            UPDATE Scenes SET Versions = '[]';
            INSERT INTO Chats (Id, PackId, Title, SessionId, Context, AssetId, VariantId, SceneId, CreatedAt, UpdatedAt)
                SELECT p.Id, p.Id, 'Pack chat', p.AgentSessionId, '{"page":"pack","packId":"' || lower(p.Id) || '"}', NULL, NULL, NULL,
                       p.CreatedAt, COALESCE((SELECT MAX(j.CreatedAt) FROM Jobs j WHERE j.PackId = p.Id AND j.Kind = 'agent-turn'), p.CreatedAt)
                FROM Packs p
                WHERE p.AgentSessionId IS NOT NULL OR EXISTS (SELECT 1 FROM Jobs j WHERE j.PackId = p.Id AND j.Kind = 'agent-turn');
            UPDATE Jobs SET ChatId = PackId WHERE Kind = 'agent-turn';
            """);

        migrationBuilder.DropIndex(
            name: "IX_ProgramVersions_AssetId_Number",
            table: "ProgramVersions");

        migrationBuilder.DropPrimaryKey(
            name: "PK_Manifests",
            table: "Manifests");

        migrationBuilder.DropColumn(
            name: "AgentSessionId",
            table: "Packs");

        migrationBuilder.DropColumn(
            name: "CurrentProgramVersionId",
            table: "Assets");

        migrationBuilder.AddPrimaryKey(
            name: "PK_Manifests",
            table: "Manifests",
            column: "VariantId");

        migrationBuilder.CreateIndex(
            name: "IX_ProgramVersions_AssetId",
            table: "ProgramVersions",
            column: "AssetId");

        migrationBuilder.CreateIndex(
            name: "IX_ProgramVersions_VariantId_Number",
            table: "ProgramVersions",
            columns: new[] { "VariantId", "Number" },
            unique: true);

        migrationBuilder.CreateIndex(
            name: "IX_Manifests_AssetId",
            table: "Manifests",
            column: "AssetId");

        migrationBuilder.CreateIndex(
            name: "IX_Jobs_ChatId",
            table: "Jobs",
            column: "ChatId");

        migrationBuilder.CreateIndex(
            name: "IX_ConceptImages_VariantId",
            table: "ConceptImages",
            column: "VariantId");

        migrationBuilder.CreateIndex(
            name: "IX_Builds_VariantId",
            table: "Builds",
            column: "VariantId");

        migrationBuilder.CreateIndex(
            name: "IX_AssetVariants_AssetId_Name",
            table: "AssetVariants",
            columns: new[] { "AssetId", "Name" },
            unique: true);

        migrationBuilder.CreateIndex(
            name: "IX_Chats_AssetId",
            table: "Chats",
            column: "AssetId");

        migrationBuilder.CreateIndex(
            name: "IX_Chats_PackId",
            table: "Chats",
            column: "PackId");

        migrationBuilder.CreateIndex(
            name: "IX_Chats_SceneId",
            table: "Chats",
            column: "SceneId");
    }

    /// <inheritdoc />
    protected override void Down(MigrationBuilder migrationBuilder)
    {
        migrationBuilder.DropTable(
            name: "AssetVariants");

        migrationBuilder.DropTable(
            name: "Chats");

        migrationBuilder.DropIndex(
            name: "IX_ProgramVersions_AssetId",
            table: "ProgramVersions");

        migrationBuilder.DropIndex(
            name: "IX_ProgramVersions_VariantId_Number",
            table: "ProgramVersions");

        migrationBuilder.DropPrimaryKey(
            name: "PK_Manifests",
            table: "Manifests");

        migrationBuilder.DropIndex(
            name: "IX_Manifests_AssetId",
            table: "Manifests");

        migrationBuilder.DropIndex(
            name: "IX_Jobs_ChatId",
            table: "Jobs");

        migrationBuilder.DropIndex(
            name: "IX_ConceptImages_VariantId",
            table: "ConceptImages");

        migrationBuilder.DropIndex(
            name: "IX_Builds_VariantId",
            table: "Builds");

        migrationBuilder.DropColumn(
            name: "Versions",
            table: "Scenes");

        migrationBuilder.DropColumn(
            name: "VariantId",
            table: "ProgramVersions");

        migrationBuilder.DropColumn(
            name: "VariantId",
            table: "Manifests");

        migrationBuilder.DropColumn(
            name: "ChatId",
            table: "Jobs");

        migrationBuilder.DropColumn(
            name: "VariantId",
            table: "ConceptImages");

        migrationBuilder.DropColumn(
            name: "BlendFileId",
            table: "Builds");

        migrationBuilder.DropColumn(
            name: "VariantId",
            table: "Builds");

        migrationBuilder.DropColumn(
            name: "DefaultVariantId",
            table: "Assets");

        migrationBuilder.AddColumn<string>(
            name: "AgentSessionId",
            table: "Packs",
            type: "TEXT",
            nullable: true);

        migrationBuilder.AddColumn<Guid>(
            name: "CurrentProgramVersionId",
            table: "Assets",
            type: "TEXT",
            nullable: true);

        migrationBuilder.AddPrimaryKey(
            name: "PK_Manifests",
            table: "Manifests",
            column: "AssetId");

        migrationBuilder.CreateIndex(
            name: "IX_ProgramVersions_AssetId_Number",
            table: "ProgramVersions",
            columns: new[] { "AssetId", "Number" },
            unique: true);
    }
}
