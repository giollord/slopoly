using System;
using Microsoft.EntityFrameworkCore.Migrations;

#nullable disable

namespace Slopoly.ApiService.Data.Migrations;

/// <inheritdoc />
public partial class _20261114180150_ScenesBudgetsSeeds : Migration
{
    /// <inheritdoc />
    protected override void Up(MigrationBuilder migrationBuilder)
    {
        migrationBuilder.AddColumn<long>(
            name: "Seed",
            table: "ConceptImages",
            type: "INTEGER",
            nullable: true);

        migrationBuilder.AddColumn<int>(
            name: "PolyBudget",
            table: "Assets",
            type: "INTEGER",
            nullable: true);

        migrationBuilder.CreateTable(
            name: "Scenes",
            columns: table => new
            {
                Id = table.Column<Guid>(type: "TEXT", nullable: false),
                PackId = table.Column<Guid>(type: "TEXT", nullable: false),
                Name = table.Column<string>(type: "TEXT", nullable: false),
                Description = table.Column<string>(type: "TEXT", nullable: false),
                Placements = table.Column<string>(type: "TEXT", nullable: false),
                GlbFileId = table.Column<Guid>(type: "TEXT", nullable: true),
                Report = table.Column<string>(type: "TEXT", nullable: true),
                UpdatedAt = table.Column<long>(type: "INTEGER", nullable: false)
            },
            constraints: table =>
            {
                table.PrimaryKey("PK_Scenes", x => x.Id);
            });

        migrationBuilder.CreateIndex(
            name: "IX_Scenes_PackId_Name",
            table: "Scenes",
            columns: new[] { "PackId", "Name" },
            unique: true);
    }

    /// <inheritdoc />
    protected override void Down(MigrationBuilder migrationBuilder)
    {
        migrationBuilder.DropTable(
            name: "Scenes");

        migrationBuilder.DropColumn(
            name: "Seed",
            table: "ConceptImages");

        migrationBuilder.DropColumn(
            name: "PolyBudget",
            table: "Assets");
    }
}
