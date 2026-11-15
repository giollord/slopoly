using System.IO.Compression;
using System.Text.Json.Nodes;
using Microsoft.AspNetCore.Mvc;
using Microsoft.EntityFrameworkCore;
using Slopoly.ApiService.Data;
using Slopoly.ApiService.Infrastructure;
using Slopoly.ApiService.Jobs;
using Slopoly.ApiService.Studio;
using Slopoly.Contracts;

namespace Slopoly.ApiService.Endpoints;

/// <summary>REST surface for the UI (open on localhost) and the workers (worker key).</summary>
public static class ApiEndpoints
{
    public static void MapStudioApi(this WebApplication app)
    {
        var api = app.MapGroup("/api");

        // Packs and style guide
        api.MapGet("/packs", (SlopolyDb db) => db.Packs.OrderByDescending(p => p.CreatedAt).ToListAsync());
        api.MapPost("/packs", (PackEdit edit, StudioService s) => s.CreatePackAsync(edit));
        api.MapGet("/packs/{id:guid}", (Guid id, StudioService s) => s.GetPackAsync(id));
        api.MapPatch("/packs/{id:guid}", (Guid id, PackEdit edit, StudioService s) => s.UpdatePackAsync(id, edit));
        api.MapDelete("/packs/{id:guid}", (Guid id, StudioService s) => s.DeletePackAsync(id));
        api.MapGet("/packs/{id:guid}/style-references", (Guid id, SlopolyDb db) => db.StyleReferences.Where(r => r.PackId == id).OrderBy(r => r.Id).ToListAsync());
        api.MapPost("/packs/{id:guid}/style-references", (Guid id, IFormFile file, StudioService s) =>
            s.AddStyleReferenceAsync(id, file.OpenReadStream(), file.FileName, file.ContentType)).DisableAntiforgery();
        api.MapDelete("/style-references/{id:guid}", (Guid id, StudioService s) => s.RemoveStyleReferenceAsync(id));

        // Assets and concepts
        api.MapGet("/packs/{id:guid}/assets", (Guid id, SlopolyDb db) => db.Assets.Where(a => a.PackId == id).OrderBy(a => a.CreatedAt).ToListAsync());
        api.MapPost("/packs/{id:guid}/assets", (Guid id, AssetCreate create, StudioService s) => s.CreateAssetAsync(id, create.Name, create.Description, create.PolyBudget));
        api.MapGet("/assets/{id:guid}", (Guid id, StudioService s) => s.GetAssetAsync(id));
        api.MapPatch("/assets/{id:guid}", (Guid id, AssetEdit edit, StudioService s) => s.UpdateAssetAsync(id, edit));
        api.MapDelete("/assets/{id:guid}", (Guid id, StudioService s) => s.DeleteAssetAsync(id));
        api.MapGet("/assets/{id:guid}/variants", (Guid id, StudioService s) => s.VariantsAsync(id));
        api.MapPost("/assets/{id:guid}/variants", (Guid id, VariantCreate create, GenerationService g) => g.CreateVariantAsync(id, create));
        api.MapGet("/variants/{id:guid}", (Guid id, StudioService s) => s.GetVariantAsync(id));
        api.MapPatch("/variants/{id:guid}", (Guid id, VariantUpdate update, StudioService s) => s.UpdateVariantAsync(id, update));
        api.MapDelete("/variants/{id:guid}", (Guid id, StudioService s) => s.DeleteVariantAsync(id));
        api.MapGet("/concepts/{id:guid}", async (Guid id, SlopolyDb db) => await db.ConceptImages.FindAsync(id) ?? throw StudioException.NotFound("Concept image"));
        api.MapDelete("/concepts/{id:guid}", (Guid id, StudioService s) => s.DeleteConceptAsync(id));
        api.MapGet("/packs/{id:guid}/concepts", (Guid id, Guid? assetId, bool? includeRejected, StudioService s) =>
            s.ListConceptsAsync(id, assetId, includeRejected ?? false));
        api.MapPut("/concepts/{id:guid}/selection", (Guid id, SelectionEdit edit, StudioService s) => s.SelectConceptAsync(id, edit));
        api.MapPost("/packs/{id:guid}/generate", (Guid id, GenerateRequest request, GenerationService g) => request.Operation switch
        {
            Workflows.StyleAnchor => g.StyleAnchorAsync(id, request.Description ?? "", request.Count, request.Seed),
            Workflows.Hero when request.AssetId is { } assetId => g.HeroAsync(assetId, request.Description, request.Count, request.Seed, request.VariantId),
            _ => throw new StudioException($"Unknown generation \"{request.Operation}\" (style-anchor, or hero with an assetId)."),
        });
        api.MapPost("/concepts/{id:guid}/revise", (Guid id, ReviseRequest request, GenerationService g) => g.ReviseAsync(id, request.Change, request.Count));
        api.MapPost("/concepts/{id:guid}/views", (Guid id, ViewsRequest request, GenerationService g) => g.ViewsAsync(id, request.FrontYaw));
        api.MapGet("/concepts/{id:guid}/views", async (Guid id, GenerationService g) => await g.ViewsOfAsync(id));
        api.MapPost("/concepts/{id:guid}/segment", (Guid id, SegmentRequest request, GenerationService g) => g.SegmentAsync(id, request.Parts));
        api.MapGet("/concepts/{id:guid}/masks", (Guid id, GenerationService g) => g.MasksOfAsync(id));

        // Manifest, programs, builds: per variant (?variantId=; the asset's default variant when omitted)
        api.MapGet("/assets/{id:guid}/manifest", async (Guid id, Guid? variantId, StudioService s, SlopolyDb db) =>
            await db.Manifests.FindAsync((await s.VariantOfAsync(id, variantId)).Id) is { } m ? Results.Ok(m) : Results.NoContent());
        api.MapPut("/assets/{id:guid}/manifest", (Guid id, Guid? variantId, JsonObject content, StudioService s) => s.SaveManifestAsync(id, variantId, content));
        api.MapGet("/assets/{id:guid}/programs", async (Guid id, Guid? variantId, int? skip, int? take, StudioService s, SlopolyDb db) =>
        {
            var variant = await s.VariantOfAsync(id, variantId);
            return await db.ProgramVersions.Where(v => v.VariantId == variant.Id).OrderByDescending(v => v.Number).PageAsync(skip ?? 0, take ?? 0);
        });
        api.MapGet("/programs/{id:guid}", async (Guid id, SlopolyDb db) => await db.ProgramVersions.FindAsync(id) ?? throw StudioException.NotFound("Program version"));
        api.MapPost("/assets/{id:guid}/programs", async (Guid id, Guid? variantId, ProgramSubmit submit, GenerationService g) =>
        {
            var (version, job) = await g.SubmitProgramAsync(id, variantId, submit.Source, submit.Note ?? "");
            return new { version, job };
        });
        api.MapPut("/assets/{id:guid}/current-version", (Guid id, CurrentVersionEdit edit, StudioService s) => s.SetCurrentVersionAsync(id, edit.VersionId));
        api.MapGet("/assets/{id:guid}/builds", async (Guid id, Guid? variantId, int? skip, int? take, StudioService s, SlopolyDb db) =>
        {
            var variant = await s.VariantOfAsync(id, variantId);
            return await db.Builds.Where(b => b.VariantId == variant.Id).OrderByDescending(b => b.CreatedAt).PageAsync(skip ?? 0, take ?? 0);
        });
        api.MapGet("/builds/{id:guid}", async (Guid id, SlopolyDb db) => await db.Builds.FindAsync(id) ?? throw StudioException.NotFound("Build"));
        // Export: the GLB (main palette embedded) plus palette_<variant>.png per palette variant, zipped.
        api.MapGet("/builds/{id:guid}/export", async (Guid id, SlopolyDb db, FileStore files) =>
        {
            var (build, name, version) = await BuildNameAsync(db, id);
            if (build.GlbFileId is not { } glb) throw new StudioException("The build has no model file.");
            return await ZipAsync(db, files, build, name + version, ($"{name}.glb", glb));
        });
        // Blender file: the .blend plus palette.png (current main texture, linked by relative path) and the palette variants.
        api.MapGet("/builds/{id:guid}/blend", async (Guid id, SlopolyDb db, FileStore files) =>
        {
            var (build, name, version) = await BuildNameAsync(db, id);
            if (build.BlendFileId is not { } blend)
                throw new StudioException("This build has no Blender file; rebuild its version to get one.", StatusCodes.Status409Conflict);
            var pack = await db.Packs.FirstAsync(p => db.Assets.Any(a => a.Id == build.AssetId && a.PackId == p.Id));
            var entries = new List<(string, Guid)> { ($"{name}.blend", blend) };
            if (pack.PaletteTextureFileId is { } texture) entries.Add(("palette.png", texture));
            return await ZipAsync(db, files, build, $"{name}{version}-blend", [.. entries]);
        });

        // Scenes
        api.MapGet("/packs/{id:guid}/scenes", (Guid id, SlopolyDb db) => db.Scenes.Where(s => s.PackId == id).OrderBy(s => s.Name).ToListAsync());
        api.MapPut("/packs/{id:guid}/scenes", (Guid id, SceneEdit edit, GenerationService g) => g.SaveSceneAsync(id, edit));
        // Variants and program versions of the assets a scene can place, for its version choices.
        api.MapGet("/packs/{id:guid}/variants", async (Guid id, SlopolyDb db) =>
            await db.AssetVariants.Where(v => db.Assets.Any(a => a.Id == v.AssetId && a.PackId == id)).OrderBy(v => v.CreatedAt).ToListAsync());
        api.MapGet("/packs/{id:guid}/programs", async (Guid id, SlopolyDb db) =>
            await db.ProgramVersions.Where(v => db.Assets.Any(a => a.Id == v.AssetId && a.PackId == id)).OrderByDescending(v => v.Number)
                .Select(v => new ProgramVersion { Id = v.Id, AssetId = v.AssetId, VariantId = v.VariantId, Number = v.Number, Note = v.Note, CreatedAt = v.CreatedAt })
                .ToListAsync());
        api.MapGet("/scenes/{id:guid}", async (Guid id, SlopolyDb db) => await db.Scenes.FindAsync(id) ?? throw StudioException.NotFound("Scene"));
        api.MapDelete("/scenes/{id:guid}", async (Guid id, SlopolyDb db, Notifier notifier) =>
        {
            var scene = await db.Scenes.FindAsync(id) ?? throw StudioException.NotFound("Scene");
            db.Scenes.Remove(scene);
            await db.SaveChangesAsync();
            await notifier.Changed<Scene>(id, scene.PackId);
        });

        // Knowledge notes (global)
        api.MapGet("/knowledge", (string? q, KnowledgeService k) => k.SearchAsync(q ?? "", 200)); // no query: every note
        api.MapGet("/knowledge/{**slug}", (string slug, KnowledgeService k) => k.ReadAsync(slug));
        api.MapPut("/knowledge/{**slug}", (string slug, KnowledgeNote note, KnowledgeService k) => k.WriteAsync(note with { Slug = slug }));
        api.MapDelete("/knowledge/{**slug}", (string slug, KnowledgeService k) => k.DeleteAsync(slug));

        // Palette
        api.MapGet("/packs/{id:guid}/palette", (Guid id, PaletteService p) => p.GetAsync(id));
        api.MapPost("/packs/{id:guid}/palette/entries", (Guid id, PaletteEntryEdit edit, PaletteService p) => p.AddEntryAsync(id, edit));
        api.MapPut("/packs/{id:guid}/palette/entries", (Guid id, List<PaletteEntryEdit> edits, PaletteService p) => p.UpsertEntriesAsync(id, edits));
        api.MapGet("/palette/entries/{id:guid}/used-by", (Guid id, PaletteService p) => p.UsedByAsync(id));
        api.MapDelete("/palette/entries/{id:guid}", (Guid id, PaletteService p) => p.DeleteEntryAsync(id));
        api.MapPut("/packs/{id:guid}/palette/variants", (Guid id, VariantEdit edit, PaletteService p) => p.UpsertVariantAsync(id, edit.Name, edit.Colors));
        api.MapDelete("/palette/variants/{id:guid}", (Guid id, PaletteService p) => p.DeleteVariantAsync(id));

        // Jobs and chat
        api.MapGet("/packs/{id:guid}/jobs", (Guid id, int? skip, int? take, SlopolyDb db) =>
            db.Jobs.Where(j => j.PackId == id).OrderByDescending(j => j.CreatedAt).PageAsync(skip ?? 0, take ?? 0));
        api.MapGet("/jobs", (Guid? packId, Guid? assetId, string? kind, SlopolyDb db) => db.Jobs
            .Where(j => (packId == null || j.PackId == packId) && (assetId == null || j.AssetId == assetId) && (kind == null || j.Kind == kind))
            .OrderByDescending(j => j.CreatedAt).Take(100).ToListAsync());
        api.MapGet("/jobs/{id:guid}", (Guid id, JobService j) => j.GetAsync(id));
        api.MapGet("/jobs/{id:guid}/events", (Guid id, SlopolyDb db) => db.JobEvents.Where(e => e.JobId == id).OrderBy(e => e.Id).ToListAsync());
        api.MapPost("/jobs/{id:guid}/cancel", (Guid id, JobService j) => j.CancelAsync(id));
        api.MapPost("/jobs/{id:guid}/retry", (Guid id, JobService j) => j.RetryAsync(id));
        api.MapGet("/chats", (Guid? packId, Guid? assetId, Guid? sceneId, int? skip, int? take, ChatService c) =>
            c.ListAsync(packId, assetId, sceneId, skip ?? 0, take ?? 0));
        api.MapPost("/chats", (ChatCreate create, ChatService c) => c.CreateAsync(create.Context));
        api.MapGet("/chats/{id:guid}", (Guid id, ChatService c) => c.GetAsync(id));
        api.MapGet("/chats/{id:guid}/turns", (Guid id, Guid? before, int? take, ChatService c) => c.TurnsAsync(id, before, take ?? 0));
        api.MapPost("/chats/{id:guid}/messages", (Guid id, ChatMessage message, ChatService c) => c.SendAsync(id, message));
        api.MapPost("/chats/{id:guid}/stop", (Guid id, ChatService c) => c.StopAsync(id));

        // Files: anyone on localhost reads; only workers upload.
        api.MapGet("/files/{id:guid}", async (Guid id, SlopolyDb db, FileStore files) =>
            await db.Files.FindAsync(id) is { } f
                ? Results.File(files.PathOf(id), f.ContentType, f.Name, enableRangeProcessing: true)
                : Results.NotFound());
        var worker = app.MapGroup("/worker"); // worker key checked by UseWorkerKey
        worker.MapPost("/files", async (IFormFile file, FileStore files, SlopolyDb db) =>
        {
            var stored = await files.AddAsync(file.OpenReadStream(), file.FileName, file.ContentType);
            await db.SaveChangesAsync();
            return stored;
        }).DisableAntiforgery();
        worker.MapGet("/jobs/{id:guid}", (Guid id, JobService j) => j.GetAsync(id));
    }

    private static string FileName(string name) =>
        string.Join("_", name.Split([.. Path.GetInvalidFileNameChars(), ' '], StringSplitOptions.RemoveEmptyEntries));

    /// <summary>A build, its file name (asset, then the variant unless it is the default) and its version suffix ("-v3").</summary>
    private static async Task<(Build Build, string Name, string Version)> BuildNameAsync(SlopolyDb db, Guid buildId)
    {
        var build = await db.Builds.FindAsync(buildId) ?? throw StudioException.NotFound("Build");
        var asset = await db.Assets.FindAsync(build.AssetId) ?? throw StudioException.NotFound("Asset");
        var variant = await db.AssetVariants.FindAsync(build.VariantId);
        var version = await db.ProgramVersions.FindAsync(build.ProgramVersionId);
        var name = FileName(asset.Name) + (variant is null || variant.Id == asset.DefaultVariantId ? "" : $"-{FileName(variant.Name)}");
        return (build, name, version is null ? "" : $"-v{version.Number}");
    }

    /// <summary>A zip of the given files plus palette_&lt;name&gt;.png per rendered palette variant of the build's pack.</summary>
    private static async Task<IResult> ZipAsync(SlopolyDb db, FileStore files, Build build, string name, params (string Entry, Guid File)[] entries)
    {
        var packId = (await db.Assets.FindAsync(build.AssetId))!.PackId;
        var variants = await db.PaletteVariants.Where(v => v.PackId == packId && v.TextureFileId != null).ToListAsync();
        var zip = new MemoryStream();
        using (var archive = new ZipArchive(zip, ZipArchiveMode.Create, leaveOpen: true))
        {
            foreach (var (entry, file) in entries) archive.CreateEntryFromFile(files.PathOf(file), entry);
            foreach (var v in variants) archive.CreateEntryFromFile(files.PathOf(v.TextureFileId!.Value), $"palette_{FileName(v.Name)}.png");
        }
        zip.Position = 0;
        return Results.File(zip, "application/zip", $"{name}.zip");
    }

    /// <summary>Maps <see cref="StudioException"/> to problem details.</summary>
    public static void UseStudioErrors(this WebApplication app) =>
        app.Use(async (context, next) =>
        {
            try { await next(context); }
            catch (StudioException ex) when (!context.Response.HasStarted)
            {
                context.Response.StatusCode = ex.Status;
                var problem = new ProblemDetails { Status = ex.Status, Title = ex.Message };
                if (ex.Code is { } code) problem.Extensions["code"] = code;
                await context.Response.WriteAsJsonAsync(problem);
            }
        });
}
