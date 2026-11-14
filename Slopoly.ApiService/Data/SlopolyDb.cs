using System.Text.Json;
using Microsoft.EntityFrameworkCore;
using Microsoft.EntityFrameworkCore.Metadata.Builders;
using Microsoft.EntityFrameworkCore.Storage.ValueConversion;
using Slopoly.Contracts;

namespace Slopoly.ApiService.Data;

public sealed class SlopolyDb(DbContextOptions<SlopolyDb> options) : DbContext(options)
{
    public DbSet<Pack> Packs => Set<Pack>();
    public DbSet<StyleReference> StyleReferences => Set<StyleReference>();
    public DbSet<Asset> Assets => Set<Asset>();
    public DbSet<ConceptImage> ConceptImages => Set<ConceptImage>();
    public DbSet<PartMask> PartMasks => Set<PartMask>();
    public DbSet<PaletteEntry> PaletteEntries => Set<PaletteEntry>();
    public DbSet<PaletteVariant> PaletteVariants => Set<PaletteVariant>();
    public DbSet<PaletteVariantColor> PaletteVariantColors => Set<PaletteVariantColor>();
    public DbSet<Manifest> Manifests => Set<Manifest>();
    public DbSet<ProgramVersion> ProgramVersions => Set<ProgramVersion>();
    public DbSet<Build> Builds => Set<Build>();
    public DbSet<Scene> Scenes => Set<Scene>();
    public DbSet<Job> Jobs => Set<Job>();
    public DbSet<JobEvent> JobEvents => Set<JobEvent>();
    public DbSet<StoredFile> Files => Set<StoredFile>();

    protected override void ConfigureConventions(ModelConfigurationBuilder builder)
    {
        // SQLite can't order or compare DateTimeOffset; store it as UTC ticks.
        builder.Properties<DateTimeOffset>().HaveConversion<DateTimeOffsetToBinaryConverter>();
        builder.Properties<DateTimeOffset?>().HaveConversion<DateTimeOffsetToBinaryConverter>();
        builder.Properties<Enum>().HaveConversion<string>();
    }

    protected override void OnModelCreating(ModelBuilder b)
    {
        b.Entity<Pack>().HasIndex(p => p.Name);
        b.Entity<StyleReference>().HasIndex(r => r.PackId);
        b.Entity<Asset>().HasIndex(a => a.PackId);
        b.Entity<ConceptImage>(e => { e.HasIndex(c => c.PackId); e.HasIndex(c => c.AssetId); e.HasIndex(c => c.SourceConceptId); });
        b.Entity<PartMask>(e => { e.HasIndex(m => m.ConceptImageId); e.Json(m => m.Bounds); e.Json(m => m.Colors); });
        b.Entity<PaletteEntry>().HasIndex(p => new { p.PackId, p.Role }).IsUnique();
        b.Entity<PaletteVariant>().HasIndex(p => new { p.PackId, p.Name }).IsUnique();
        b.Entity<PaletteVariantColor>().HasKey(c => new { c.VariantId, c.EntryId });
        b.Entity<Manifest>(e => { e.HasKey(m => m.AssetId); e.Json(m => m.Content); });
        b.Entity<ProgramVersion>().HasIndex(v => new { v.AssetId, v.Number }).IsUnique();
        b.Entity<Build>(e => { e.HasIndex(x => x.AssetId); e.HasIndex(x => x.JobId); e.Json(x => x.Report); });
        b.Entity<Scene>(e => { e.HasIndex(x => new { x.PackId, x.Name }).IsUnique(); e.Json(x => x.Placements); e.Json(x => x.Report); });
        b.Entity<Job>(e => { e.HasIndex(j => j.PackId); e.HasIndex(j => j.AssetId); e.Json(j => j.Inputs); e.Json(j => j.Outputs); });
        b.Entity<JobEvent>(e => { e.HasIndex(x => x.JobId); e.Json(x => x.Data); });
    }
}

internal static class JsonColumn
{
    private static readonly JsonSerializerOptions Options = new(JsonSerializerDefaults.Web);

    /// <summary>Stores a property as JSON text.</summary>
    public static void Json<TEntity, TProperty>(this EntityTypeBuilder<TEntity> entity,
        System.Linq.Expressions.Expression<Func<TEntity, TProperty>> property) where TEntity : class =>
        entity.Property(property).HasConversion(
            v => JsonSerializer.Serialize(v, Options),
            v => JsonSerializer.Deserialize<TProperty>(v, Options)!,
            new Microsoft.EntityFrameworkCore.ChangeTracking.ValueComparer<TProperty>(
                (a, c) => JsonSerializer.Serialize(a, Options) == JsonSerializer.Serialize(c, Options),
                v => JsonSerializer.Serialize(v, Options).GetHashCode(),
                v => JsonSerializer.Deserialize<TProperty>(JsonSerializer.Serialize(v, Options), Options)!));
}
