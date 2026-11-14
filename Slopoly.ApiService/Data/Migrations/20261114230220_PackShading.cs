using Microsoft.EntityFrameworkCore.Migrations;

#nullable disable

namespace Slopoly.ApiService.Data.Migrations;

/// <inheritdoc />
public partial class _20261114230220_PackShading : Migration
{
    /// <inheritdoc />
    protected override void Up(MigrationBuilder migrationBuilder)
    {
        migrationBuilder.AddColumn<double>(
            name: "HardEdgeAngle",
            table: "Packs",
            type: "REAL",
            nullable: false,
            defaultValue: 60.0);

        migrationBuilder.AddColumn<double>(
            name: "ShadeStrength",
            table: "Packs",
            type: "REAL",
            nullable: false,
            defaultValue: 0.5);

        migrationBuilder.AddColumn<string>(
            name: "ShadingMode",
            table: "Packs",
            type: "TEXT",
            nullable: false,
            defaultValue: "Flat");
    }

    /// <inheritdoc />
    protected override void Down(MigrationBuilder migrationBuilder)
    {
        migrationBuilder.DropColumn(
            name: "HardEdgeAngle",
            table: "Packs");

        migrationBuilder.DropColumn(
            name: "ShadeStrength",
            table: "Packs");

        migrationBuilder.DropColumn(
            name: "ShadingMode",
            table: "Packs");
    }
}
