namespace Slopoly.Contracts;

// Request and response shapes of the REST API (shared by the API, the UI and the tests).

public sealed record AssetCreate(string Name, string Description, int? PolyBudget = null);

/// <summary>Null keeps a value; a PolyBudget of 0 clears the asset's own budget.</summary>
public sealed record AssetEdit(string? Name, string? Description, int? PolyBudget);

public sealed record SelectionEdit(Selection Selection);

public sealed record GenerateRequest(string Operation, Guid? AssetId, string? Description, int Count = 1, long? Seed = null);

public sealed record SegmentRequest(List<string> Parts);

public sealed record ProgramSubmit(string Source, string? Note);

public sealed record CurrentVersionEdit(Guid VersionId);

public sealed record ChatMessage(string Message);

public sealed record VariantEdit(string Name, List<VariantColorEdit> Colors);

public sealed record ChatTurn(Job Job, List<JobEvent> Events);

public sealed record PackEdit(string? Name, string? Instructions, string? StyleText, int? PolyBudget);

/// <summary>An entry as the geometry worker and the agent see it.</summary>
public sealed record PaletteSlot(Guid Id, string Role, PaletteKind Kind, int Slot, string Color, string? Color2);

public sealed record PaletteEntryEdit(string Role, PaletteKind? Kind, string? Color, string? Color2);

public sealed record VariantColorEdit(string Role, string Color, string? Color2);

public sealed record PaletteView(List<PaletteEntry> Entries, List<VariantView> Variants, Guid? TextureFileId);

public sealed record VariantView(Guid Id, string Name, Guid? TextureFileId, List<PaletteSlot> Entries);

public sealed record ReviseRequest(string? Change, int Count = 2);

public sealed record SceneEdit(string Name, string? Description, List<ScenePlacement> Placements);

/// <summary>A knowledge note: front matter plus Markdown body.</summary>
public sealed record KnowledgeNote(string Slug, string Title, List<string> Tags, string Summary, string Body);

public sealed record KnowledgeHit(string Slug, string Title, List<string> Tags, string Summary, double Score);
