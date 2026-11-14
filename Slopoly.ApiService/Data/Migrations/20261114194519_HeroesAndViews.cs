using System;
using Microsoft.EntityFrameworkCore.Migrations;

#nullable disable

namespace Slopoly.ApiService.Data.Migrations;

/// <inheritdoc />
public partial class _20261114194519_HeroesAndViews : Migration
{
    /// <inheritdoc />
    protected override void Up(MigrationBuilder migrationBuilder)
    {
        // Turnaround sheets are gone (design section 4). Back up <data-dir>/slopoly.db first: this deletes them and their masks.
        migrationBuilder.Sql("DELETE FROM PartMasks WHERE ConceptImageId IN (SELECT Id FROM ConceptImages WHERE Kind = 'Turnaround');");
        migrationBuilder.Sql("DELETE FROM ConceptImages WHERE Kind = 'Turnaround';");

        migrationBuilder.DropColumn(
            name: "Views",
            table: "ConceptImages");

        migrationBuilder.AddColumn<string>(
            name: "Front",
            table: "ConceptImages",
            type: "TEXT",
            nullable: true);

        migrationBuilder.AddColumn<double>(
            name: "FrontYaw",
            table: "ConceptImages",
            type: "REAL",
            nullable: true);

        migrationBuilder.AddColumn<Guid>(
            name: "MaskFileId",
            table: "ConceptImages",
            type: "TEXT",
            nullable: true);

        migrationBuilder.AddColumn<Guid>(
            name: "SourceConceptId",
            table: "ConceptImages",
            type: "TEXT",
            nullable: true);

        migrationBuilder.AddColumn<string>(
            name: "View",
            table: "ConceptImages",
            type: "TEXT",
            nullable: true);

        migrationBuilder.AddColumn<long>(
            name: "ViewsSeed",
            table: "ConceptImages",
            type: "INTEGER",
            nullable: true);

        migrationBuilder.CreateIndex(
            name: "IX_ConceptImages_SourceConceptId",
            table: "ConceptImages",
            column: "SourceConceptId");
    }

    /// <inheritdoc />
    protected override void Down(MigrationBuilder migrationBuilder)
    {
        migrationBuilder.DropIndex(
            name: "IX_ConceptImages_SourceConceptId",
            table: "ConceptImages");

        migrationBuilder.DropColumn(
            name: "Front",
            table: "ConceptImages");

        migrationBuilder.DropColumn(
            name: "FrontYaw",
            table: "ConceptImages");

        migrationBuilder.DropColumn(
            name: "MaskFileId",
            table: "ConceptImages");

        migrationBuilder.DropColumn(
            name: "SourceConceptId",
            table: "ConceptImages");

        migrationBuilder.DropColumn(
            name: "View",
            table: "ConceptImages");

        migrationBuilder.DropColumn(
            name: "ViewsSeed",
            table: "ConceptImages");

        migrationBuilder.AddColumn<string>(
            name: "Views",
            table: "ConceptImages",
            type: "TEXT",
            nullable: false,
            defaultValue: "");
    }
}
