using System.Text.Json.Nodes;

namespace Slopoly.Contracts;

// Persistent records. They are EF Core entities in the API and plain JSON DTOs for the UI, so they carry foreign-key
// ids only (no navigation properties).

public sealed class Pack
{
    public Guid Id { get; set; } = Guid.CreateVersion7();
    public string Name { get; set; } = "";
    public string Instructions { get; set; } = "";
    public string StyleText { get; set; } = "";
    public int PolyBudget { get; set; } = 2000;
    /// <summary>Normals of every build: flat (all edges hard) or smooth (edges over <see cref="HardEdgeAngle"/> stay hard).</summary>
    public ShadingMode ShadingMode { get; set; } = ShadingMode.Flat;
    /// <summary>Degrees; in smooth mode, edges whose faces meet at more than this stay hard.</summary>
    public double HardEdgeAngle { get; set; } = 60;
    /// <summary>0..1 strength of the baked vertex shade (ambient occlusion and edge wear); 0 turns it off.</summary>
    public double ShadeStrength { get; set; } = 0.5;
    /// <summary>Claude Code session id of the pack's chat; set by the agent worker.</summary>
    public string? AgentSessionId { get; set; }
    /// <summary>Rendered main palette texture; re-rendered on palette edits.</summary>
    public Guid? PaletteTextureFileId { get; set; }
    public DateTimeOffset CreatedAt { get; set; } = DateTimeOffset.UtcNow;
}

public sealed class StyleReference
{
    public Guid Id { get; set; } = Guid.CreateVersion7();
    public Guid PackId { get; set; }
    public Guid FileId { get; set; }
    public string Label { get; set; } = "";
}

public enum AssetStatus { Concept, Manifest, Built, Validated }

public enum ShadingMode { Flat, Smooth }

public sealed class Asset
{
    public Guid Id { get; set; } = Guid.CreateVersion7();
    public Guid PackId { get; set; }
    public string Name { get; set; } = "";
    public string Description { get; set; } = "";
    public AssetStatus Status { get; set; }
    /// <summary>Triangle budget of this asset's builds; null uses the pack's budget.</summary>
    public int? PolyBudget { get; set; }
    public Guid? CurrentProgramVersionId { get; set; }
    public DateTimeOffset CreatedAt { get; set; } = DateTimeOffset.UtcNow;
}

/// <summary>Anchor: a scene that sets the pack's style. Hero: one asset, three-quarter front view. View: an
/// orthographic front, side, top or back image rendered from a hero's splat.</summary>
public enum ConceptKind { Anchor, Hero, View }

public enum Selection { None, Picked, Rejected }

/// <summary>A rectangle in image pixels.</summary>
public sealed record Rect(int X, int Y, int Width, int Height);

public sealed class ConceptImage
{
    public Guid Id { get; set; } = Guid.CreateVersion7();
    public Guid PackId { get; set; }
    public Guid? AssetId { get; set; }
    public Guid FileId { get; set; }
    public Guid? JobId { get; set; }
    public ConceptKind Kind { get; set; }
    public Selection Selection { get; set; }
    /// <summary>Sampler seed the image was generated with (reported by the comfy worker).</summary>
    public long? Seed { get; set; }
    public int Width { get; set; }
    public int Height { get; set; }
    /// <summary>A view's name: front, side, top or back.</summary>
    public string? View { get; set; }
    /// <summary>A view's hero.</summary>
    public Guid? SourceConceptId { get; set; }
    /// <summary>A view's object silhouette (white = object), from the render.</summary>
    public Guid? MaskFileId { get; set; }
    /// <summary>A hero's front direction in degrees on the splat turntable, set by its views job.</summary>
    public double? FrontYaw { get; set; }
    /// <summary>How a hero's front was found: detected (symmetry), assumed (no symmetry, so the hero's own direction)
    /// or given (by the user).</summary>
    public string? Front { get; set; }
    /// <summary>The seed of a hero's views job; the same seed rebuilds the same splat.</summary>
    public long? ViewsSeed { get; set; }
    public DateTimeOffset CreatedAt { get; set; } = DateTimeOffset.UtcNow;
}

public sealed record MeasuredColor(string Hex, double Coverage);

/// <summary>One part's mask in one view image, with its measured colours. Part "object" is the view's silhouette.</summary>
public sealed class PartMask
{
    public Guid Id { get; set; } = Guid.CreateVersion7();
    public Guid ConceptImageId { get; set; }
    public Guid JobId { get; set; }
    public string Part { get; set; } = "";
    public string View { get; set; } = "";
    public Guid FileId { get; set; }
    /// <summary>Bounding box in view image pixels.</summary>
    public Rect Bounds { get; set; } = new(0, 0, 0, 0);
    public int Area { get; set; }
    public List<MeasuredColor> Colors { get; set; } = [];
}

public static class ViewNames
{
    public static readonly string[] All = ["front", "side", "top", "back"];
}

public static class PartMasks
{
    /// <summary>The part name of a view's whole-object silhouette.</summary>
    public const string Object = "object";
}

public enum PaletteKind { Solid, Gradient }

public sealed class PaletteEntry
{
    public Guid Id { get; set; } = Guid.CreateVersion7();
    public Guid PackId { get; set; }
    /// <summary>Usage name ("wall base"); a colour name only for colours fixed across palettes.</summary>
    public string Role { get; set; } = "";
    public PaletteKind Kind { get; set; }
    /// <summary>Assigned once; solid and gradient slots are numbered separately.</summary>
    public int Slot { get; set; }
    public string Color { get; set; } = "#808080";
    /// <summary>Gradient end colour.</summary>
    public string? Color2 { get; set; }
}

public sealed class PaletteVariant
{
    public Guid Id { get; set; } = Guid.CreateVersion7();
    public Guid PackId { get; set; }
    public string Name { get; set; } = "";
    public Guid? TextureFileId { get; set; }
}

public sealed class PaletteVariantColor
{
    public Guid VariantId { get; set; }
    public Guid EntryId { get; set; }
    public string Color { get; set; } = "#808080";
    public string? Color2 { get; set; }
}

public sealed class Manifest
{
    public Guid AssetId { get; set; }
    public JsonObject Content { get; set; } = [];
    public DateTimeOffset UpdatedAt { get; set; } = DateTimeOffset.UtcNow;
}

public sealed class ProgramVersion
{
    public Guid Id { get; set; } = Guid.CreateVersion7();
    public Guid AssetId { get; set; }
    public int Number { get; set; }
    public string Source { get; set; } = "";
    public string Note { get; set; } = "";
    public DateTimeOffset CreatedAt { get; set; } = DateTimeOffset.UtcNow;
}

public sealed class Build
{
    public Guid Id { get; set; } = Guid.CreateVersion7();
    public Guid AssetId { get; set; }
    public Guid ProgramVersionId { get; set; }
    public Guid JobId { get; set; }
    public Guid? GlbFileId { get; set; }
    public bool Validated { get; set; }
    /// <summary>Validator report, silhouette and colour scores (see the geometry worker).</summary>
    public JsonObject? Report { get; set; }
    /// <summary>Palette entry ids the build's faces use.</summary>
    public List<Guid> PaletteEntryIds { get; set; } = [];
    public DateTimeOffset CreatedAt { get; set; } = DateTimeOffset.UtcNow;
}

/// <summary>Built assets of a pack placed together; built into one GLB with a placement report.</summary>
public sealed class Scene
{
    public Guid Id { get; set; } = Guid.CreateVersion7();
    public Guid PackId { get; set; }
    public string Name { get; set; } = "";
    public string Description { get; set; } = "";
    public List<ScenePlacement> Placements { get; set; } = [];
    public Guid? GlbFileId { get; set; }
    /// <summary>Scene build report: placements (bounds, grounded) and overlaps.</summary>
    public JsonObject? Report { get; set; }
    public DateTimeOffset UpdatedAt { get; set; } = DateTimeOffset.UtcNow;
}

/// <summary>One asset in a scene. Metres, Y up; rotation in Euler degrees (X, then Y, then Z).</summary>
public sealed record ScenePlacement(string Name, Guid AssetId, double[] At, double[]? Rot = null, double Scale = 1);

public enum JobState { Queued, Running, Succeeded, Failed, Cancelled }

public sealed class Job
{
    public Guid Id { get; set; } = Guid.CreateVersion7();
    /// <summary>Queue kind: comfy, build, palette-render, agent-turn.</summary>
    public string Kind { get; set; } = "";
    /// <summary>Sub-operation, e.g. the ComfyUI workflow name.</summary>
    public string? Operation { get; set; }
    public Guid? PackId { get; set; }
    public Guid? AssetId { get; set; }
    public JsonObject Inputs { get; set; } = [];
    public JobState State { get; set; }
    public int Attempt { get; set; }
    public double? Progress { get; set; }
    public string? Error { get; set; }
    public string? ErrorCode { get; set; }
    public JsonObject? Outputs { get; set; }
    public DateTimeOffset CreatedAt { get; set; } = DateTimeOffset.UtcNow;
    public DateTimeOffset? StartedAt { get; set; }
    public DateTimeOffset? FinishedAt { get; set; }
}

public sealed class JobEvent
{
    public long Id { get; set; }
    public Guid JobId { get; set; }
    public string Type { get; set; } = "";
    public JsonObject? Data { get; set; }
    public DateTimeOffset At { get; set; } = DateTimeOffset.UtcNow;
}

public sealed class StoredFile
{
    public Guid Id { get; set; } = Guid.CreateVersion7();
    public string Name { get; set; } = "";
    public string ContentType { get; set; } = "application/octet-stream";
    public long Size { get; set; }
    public string Sha256 { get; set; } = "";
    public DateTimeOffset CreatedAt { get; set; } = DateTimeOffset.UtcNow;
}
