namespace Slopoly.Contracts;

// Request and response shapes of the REST API (shared by the API, the UI and the tests).

public sealed record AssetCreate(string Name, string Description, int? PolyBudget = null);

/// <summary>Null keeps a value; a PolyBudget of 0 clears the asset's own budget.</summary>
public sealed record AssetEdit(string? Name, string? Description, int? PolyBudget);

/// <summary>Picking a hero whose variant already has a reference needs OnConflict: "replace" or "newVariant" (with VariantName).</summary>
public sealed record SelectionEdit(Selection Selection, string? OnConflict = null, string? VariantName = null);

public static class SelectionConflicts
{
    public const string Replace = "replace", NewVariant = "newVariant";
    /// <summary>Error code of a pick refused because the variant has a reference hero.</summary>
    public const string ReferenceExists = "reference_exists";
}

/// <summary>A new variant: empty, a copy of another variant's manifest and current program, or from a hero image.</summary>
public sealed record VariantCreate(string Name, Guid? FromVariantId = null, Guid? FromHeroId = null);

/// <summary>Null keeps a value.</summary>
public sealed record VariantUpdate(string? Name, bool? MakeDefault);

/// <summary>One page of a history list, newest first.</summary>
public sealed record Page<T>(List<T> Items, int Total);

public sealed record ChatCreate(ChatContext Context);

public sealed record GenerateRequest(string Operation, Guid? AssetId, string? Description, int Count = 1, long? Seed = null, Guid? VariantId = null);

public sealed record SegmentRequest(List<string> Parts);

/// <summary>Make a picked hero's views; with a front yaw, remake them from the same splat with that front.</summary>
public sealed record ViewsRequest(double? FrontYaw = null);

public sealed record ProgramSubmit(string Source, string? Note);

public sealed record CurrentVersionEdit(Guid VersionId);

/// <summary>A message and the page the user sends it from.</summary>
public sealed record ChatMessage(string Message, ChatContext? Context = null);

public sealed record VariantEdit(string Name, List<VariantColorEdit> Colors);

public sealed record ChatTurn(Job Job, List<JobEvent> Events);

/// <summary>Null keeps a value.</summary>
public sealed record PackEdit(string? Name, string? Instructions, string? StyleText, int? PolyBudget,
    ShadingMode? ShadingMode = null, double? HardEdgeAngle = null, double? ShadeStrength = null);

/// <summary>An entry as the geometry worker and the agent see it.</summary>
public sealed record PaletteSlot(Guid Id, string Role, PaletteKind Kind, int Slot, string Color, string? Color2);

public sealed record PaletteEntryEdit(string Role, PaletteKind? Kind, string? Color, string? Color2);

public sealed record VariantColorEdit(string Role, string Color, string? Color2);

public sealed record PaletteView(List<PaletteEntry> Entries, List<VariantView> Variants, Guid? TextureFileId);

public sealed record VariantView(Guid Id, string Name, Guid? TextureFileId, List<PaletteSlot> Entries);

public sealed record ReviseRequest(string? Change, int Count = 2);

public sealed record SceneEdit(string Name, string? Description, List<ScenePlacement> Placements, List<SceneVersion>? Versions = null);

/// <summary>A knowledge note: front matter plus Markdown body.</summary>
public sealed record KnowledgeNote(string Slug, string Title, List<string> Tags, string Summary, string Body);

public sealed record KnowledgeHit(string Slug, string Title, List<string> Tags, string Summary, double Score);
