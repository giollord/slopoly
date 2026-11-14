using System;
using Microsoft.EntityFrameworkCore.Migrations;

#nullable disable

namespace Slopoly.ApiService.Data.Migrations;

/// <inheritdoc />
public partial class _20261113234255_Initial : Migration
{
    /// <inheritdoc />
    protected override void Up(MigrationBuilder migrationBuilder)
    {
        migrationBuilder.CreateTable(
            name: "Assets",
            columns: table => new
            {
                Id = table.Column<Guid>(type: "TEXT", nullable: false),
                PackId = table.Column<Guid>(type: "TEXT", nullable: false),
                Name = table.Column<string>(type: "TEXT", nullable: false),
                Description = table.Column<string>(type: "TEXT", nullable: false),
                Status = table.Column<string>(type: "TEXT", nullable: false),
                CurrentProgramVersionId = table.Column<Guid>(type: "TEXT", nullable: true),
                CreatedAt = table.Column<long>(type: "INTEGER", nullable: false)
            },
            constraints: table =>
            {
                table.PrimaryKey("PK_Assets", x => x.Id);
            });

        migrationBuilder.CreateTable(
            name: "Builds",
            columns: table => new
            {
                Id = table.Column<Guid>(type: "TEXT", nullable: false),
                AssetId = table.Column<Guid>(type: "TEXT", nullable: false),
                ProgramVersionId = table.Column<Guid>(type: "TEXT", nullable: false),
                JobId = table.Column<Guid>(type: "TEXT", nullable: false),
                GlbFileId = table.Column<Guid>(type: "TEXT", nullable: true),
                Validated = table.Column<bool>(type: "INTEGER", nullable: false),
                Report = table.Column<string>(type: "TEXT", nullable: true),
                PaletteEntryIds = table.Column<string>(type: "TEXT", nullable: false),
                CreatedAt = table.Column<long>(type: "INTEGER", nullable: false)
            },
            constraints: table =>
            {
                table.PrimaryKey("PK_Builds", x => x.Id);
            });

        migrationBuilder.CreateTable(
            name: "ConceptImages",
            columns: table => new
            {
                Id = table.Column<Guid>(type: "TEXT", nullable: false),
                PackId = table.Column<Guid>(type: "TEXT", nullable: false),
                AssetId = table.Column<Guid>(type: "TEXT", nullable: true),
                FileId = table.Column<Guid>(type: "TEXT", nullable: false),
                JobId = table.Column<Guid>(type: "TEXT", nullable: true),
                Kind = table.Column<string>(type: "TEXT", nullable: false),
                Selection = table.Column<string>(type: "TEXT", nullable: false),
                Width = table.Column<int>(type: "INTEGER", nullable: false),
                Height = table.Column<int>(type: "INTEGER", nullable: false),
                Views = table.Column<string>(type: "TEXT", nullable: false),
                CreatedAt = table.Column<long>(type: "INTEGER", nullable: false)
            },
            constraints: table =>
            {
                table.PrimaryKey("PK_ConceptImages", x => x.Id);
            });

        migrationBuilder.CreateTable(
            name: "Files",
            columns: table => new
            {
                Id = table.Column<Guid>(type: "TEXT", nullable: false),
                Name = table.Column<string>(type: "TEXT", nullable: false),
                ContentType = table.Column<string>(type: "TEXT", nullable: false),
                Size = table.Column<long>(type: "INTEGER", nullable: false),
                Sha256 = table.Column<string>(type: "TEXT", nullable: false),
                CreatedAt = table.Column<long>(type: "INTEGER", nullable: false)
            },
            constraints: table =>
            {
                table.PrimaryKey("PK_Files", x => x.Id);
            });

        migrationBuilder.CreateTable(
            name: "JobEvents",
            columns: table => new
            {
                Id = table.Column<long>(type: "INTEGER", nullable: false)
                    .Annotation("Sqlite:Autoincrement", true),
                JobId = table.Column<Guid>(type: "TEXT", nullable: false),
                Type = table.Column<string>(type: "TEXT", nullable: false),
                Data = table.Column<string>(type: "TEXT", nullable: true),
                At = table.Column<long>(type: "INTEGER", nullable: false)
            },
            constraints: table =>
            {
                table.PrimaryKey("PK_JobEvents", x => x.Id);
            });

        migrationBuilder.CreateTable(
            name: "Jobs",
            columns: table => new
            {
                Id = table.Column<Guid>(type: "TEXT", nullable: false),
                Kind = table.Column<string>(type: "TEXT", nullable: false),
                Operation = table.Column<string>(type: "TEXT", nullable: true),
                PackId = table.Column<Guid>(type: "TEXT", nullable: true),
                AssetId = table.Column<Guid>(type: "TEXT", nullable: true),
                Inputs = table.Column<string>(type: "TEXT", nullable: false),
                State = table.Column<string>(type: "TEXT", nullable: false),
                Attempt = table.Column<int>(type: "INTEGER", nullable: false),
                Progress = table.Column<double>(type: "REAL", nullable: true),
                Error = table.Column<string>(type: "TEXT", nullable: true),
                ErrorCode = table.Column<string>(type: "TEXT", nullable: true),
                Outputs = table.Column<string>(type: "TEXT", nullable: true),
                CreatedAt = table.Column<long>(type: "INTEGER", nullable: false),
                StartedAt = table.Column<long>(type: "INTEGER", nullable: true),
                FinishedAt = table.Column<long>(type: "INTEGER", nullable: true)
            },
            constraints: table =>
            {
                table.PrimaryKey("PK_Jobs", x => x.Id);
            });

        migrationBuilder.CreateTable(
            name: "Manifests",
            columns: table => new
            {
                AssetId = table.Column<Guid>(type: "TEXT", nullable: false),
                Content = table.Column<string>(type: "TEXT", nullable: false),
                UpdatedAt = table.Column<long>(type: "INTEGER", nullable: false)
            },
            constraints: table =>
            {
                table.PrimaryKey("PK_Manifests", x => x.AssetId);
            });

        migrationBuilder.CreateTable(
            name: "Packs",
            columns: table => new
            {
                Id = table.Column<Guid>(type: "TEXT", nullable: false),
                Name = table.Column<string>(type: "TEXT", nullable: false),
                Instructions = table.Column<string>(type: "TEXT", nullable: false),
                StyleText = table.Column<string>(type: "TEXT", nullable: false),
                PolyBudget = table.Column<int>(type: "INTEGER", nullable: false),
                AgentSessionId = table.Column<string>(type: "TEXT", nullable: true),
                PaletteTextureFileId = table.Column<Guid>(type: "TEXT", nullable: true),
                CreatedAt = table.Column<long>(type: "INTEGER", nullable: false)
            },
            constraints: table =>
            {
                table.PrimaryKey("PK_Packs", x => x.Id);
            });

        migrationBuilder.CreateTable(
            name: "PaletteEntries",
            columns: table => new
            {
                Id = table.Column<Guid>(type: "TEXT", nullable: false),
                PackId = table.Column<Guid>(type: "TEXT", nullable: false),
                Role = table.Column<string>(type: "TEXT", nullable: false),
                Kind = table.Column<string>(type: "TEXT", nullable: false),
                Slot = table.Column<int>(type: "INTEGER", nullable: false),
                Color = table.Column<string>(type: "TEXT", nullable: false),
                Color2 = table.Column<string>(type: "TEXT", nullable: true)
            },
            constraints: table =>
            {
                table.PrimaryKey("PK_PaletteEntries", x => x.Id);
            });

        migrationBuilder.CreateTable(
            name: "PaletteVariantColors",
            columns: table => new
            {
                VariantId = table.Column<Guid>(type: "TEXT", nullable: false),
                EntryId = table.Column<Guid>(type: "TEXT", nullable: false),
                Color = table.Column<string>(type: "TEXT", nullable: false),
                Color2 = table.Column<string>(type: "TEXT", nullable: true)
            },
            constraints: table =>
            {
                table.PrimaryKey("PK_PaletteVariantColors", x => new { x.VariantId, x.EntryId });
            });

        migrationBuilder.CreateTable(
            name: "PaletteVariants",
            columns: table => new
            {
                Id = table.Column<Guid>(type: "TEXT", nullable: false),
                PackId = table.Column<Guid>(type: "TEXT", nullable: false),
                Name = table.Column<string>(type: "TEXT", nullable: false),
                TextureFileId = table.Column<Guid>(type: "TEXT", nullable: true)
            },
            constraints: table =>
            {
                table.PrimaryKey("PK_PaletteVariants", x => x.Id);
            });

        migrationBuilder.CreateTable(
            name: "PartMasks",
            columns: table => new
            {
                Id = table.Column<Guid>(type: "TEXT", nullable: false),
                ConceptImageId = table.Column<Guid>(type: "TEXT", nullable: false),
                JobId = table.Column<Guid>(type: "TEXT", nullable: false),
                Part = table.Column<string>(type: "TEXT", nullable: false),
                View = table.Column<string>(type: "TEXT", nullable: false),
                FileId = table.Column<Guid>(type: "TEXT", nullable: false),
                Bounds = table.Column<string>(type: "TEXT", nullable: false),
                Area = table.Column<int>(type: "INTEGER", nullable: false),
                Colors = table.Column<string>(type: "TEXT", nullable: false)
            },
            constraints: table =>
            {
                table.PrimaryKey("PK_PartMasks", x => x.Id);
            });

        migrationBuilder.CreateTable(
            name: "ProgramVersions",
            columns: table => new
            {
                Id = table.Column<Guid>(type: "TEXT", nullable: false),
                AssetId = table.Column<Guid>(type: "TEXT", nullable: false),
                Number = table.Column<int>(type: "INTEGER", nullable: false),
                Source = table.Column<string>(type: "TEXT", nullable: false),
                Note = table.Column<string>(type: "TEXT", nullable: false),
                CreatedAt = table.Column<long>(type: "INTEGER", nullable: false)
            },
            constraints: table =>
            {
                table.PrimaryKey("PK_ProgramVersions", x => x.Id);
            });

        migrationBuilder.CreateTable(
            name: "StyleReferences",
            columns: table => new
            {
                Id = table.Column<Guid>(type: "TEXT", nullable: false),
                PackId = table.Column<Guid>(type: "TEXT", nullable: false),
                FileId = table.Column<Guid>(type: "TEXT", nullable: false),
                Label = table.Column<string>(type: "TEXT", nullable: false)
            },
            constraints: table =>
            {
                table.PrimaryKey("PK_StyleReferences", x => x.Id);
            });

        migrationBuilder.CreateIndex(
            name: "IX_Assets_PackId",
            table: "Assets",
            column: "PackId");

        migrationBuilder.CreateIndex(
            name: "IX_Builds_AssetId",
            table: "Builds",
            column: "AssetId");

        migrationBuilder.CreateIndex(
            name: "IX_Builds_JobId",
            table: "Builds",
            column: "JobId");

        migrationBuilder.CreateIndex(
            name: "IX_ConceptImages_AssetId",
            table: "ConceptImages",
            column: "AssetId");

        migrationBuilder.CreateIndex(
            name: "IX_ConceptImages_PackId",
            table: "ConceptImages",
            column: "PackId");

        migrationBuilder.CreateIndex(
            name: "IX_JobEvents_JobId",
            table: "JobEvents",
            column: "JobId");

        migrationBuilder.CreateIndex(
            name: "IX_Jobs_AssetId",
            table: "Jobs",
            column: "AssetId");

        migrationBuilder.CreateIndex(
            name: "IX_Jobs_PackId",
            table: "Jobs",
            column: "PackId");

        migrationBuilder.CreateIndex(
            name: "IX_Packs_Name",
            table: "Packs",
            column: "Name");

        migrationBuilder.CreateIndex(
            name: "IX_PaletteEntries_PackId_Role",
            table: "PaletteEntries",
            columns: new[] { "PackId", "Role" },
            unique: true);

        migrationBuilder.CreateIndex(
            name: "IX_PaletteVariants_PackId_Name",
            table: "PaletteVariants",
            columns: new[] { "PackId", "Name" },
            unique: true);

        migrationBuilder.CreateIndex(
            name: "IX_PartMasks_ConceptImageId",
            table: "PartMasks",
            column: "ConceptImageId");

        migrationBuilder.CreateIndex(
            name: "IX_ProgramVersions_AssetId_Number",
            table: "ProgramVersions",
            columns: new[] { "AssetId", "Number" },
            unique: true);

        migrationBuilder.CreateIndex(
            name: "IX_StyleReferences_PackId",
            table: "StyleReferences",
            column: "PackId");
    }

    /// <inheritdoc />
    protected override void Down(MigrationBuilder migrationBuilder)
    {
        migrationBuilder.DropTable(
            name: "Assets");

        migrationBuilder.DropTable(
            name: "Builds");

        migrationBuilder.DropTable(
            name: "ConceptImages");

        migrationBuilder.DropTable(
            name: "Files");

        migrationBuilder.DropTable(
            name: "JobEvents");

        migrationBuilder.DropTable(
            name: "Jobs");

        migrationBuilder.DropTable(
            name: "Manifests");

        migrationBuilder.DropTable(
            name: "Packs");

        migrationBuilder.DropTable(
            name: "PaletteEntries");

        migrationBuilder.DropTable(
            name: "PaletteVariantColors");

        migrationBuilder.DropTable(
            name: "PaletteVariants");

        migrationBuilder.DropTable(
            name: "PartMasks");

        migrationBuilder.DropTable(
            name: "ProgramVersions");

        migrationBuilder.DropTable(
            name: "StyleReferences");
    }
}
