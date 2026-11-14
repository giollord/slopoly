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
        api.MapGet("/concepts/{id:guid}", async (Guid id, SlopolyDb db) => await db.ConceptImages.FindAsync(id) ?? throw StudioException.NotFound("Concept image"));
        api.MapDelete("/concepts/{id:guid}", (Guid id, StudioService s) => s.DeleteConceptAsync(id));
        api.MapGet("/packs/{id:guid}/concepts", (Guid id, Guid? assetId, bool? includeRejected, StudioService s) =>
            s.ListConceptsAsync(id, assetId, includeRejected ?? false));
        api.MapPut("/concepts/{id:guid}/selection", (Guid id, SelectionEdit edit, StudioService s) => s.SelectConceptAsync(id, edit.Selection));
        api.MapPost("/packs/{id:guid}/generate", (Guid id, GenerateRequest request, GenerationService g) => request.Operation switch
        {
            Workflows.StyleAnchor => g.StyleAnchorAsync(id, request.Description ?? "", request.Count, request.Seed),
            Workflows.Hero when request.AssetId is { } assetId => g.HeroAsync(assetId, request.Description, request.Count, request.Seed),
            _ => throw new StudioException($"Unknown generation \"{request.Operation}\" (style-anchor, or hero with an assetId)."),
        });
        api.MapPost("/concepts/{id:guid}/revise", (Guid id, ReviseRequest request, GenerationService g) => g.ReviseAsync(id, request.Change, request.Count));
        api.MapPost("/concepts/{id:guid}/views", (Guid id, ViewsRequest request, GenerationService g) => g.ViewsAsync(id, request.FrontYaw));
        api.MapGet("/concepts/{id:guid}/views", async (Guid id, GenerationService g) => await g.ViewsOfAsync(id));
        api.MapPost("/concepts/{id:guid}/segment", (Guid id, SegmentRequest request, GenerationService g) => g.SegmentAsync(id, request.Parts));
        api.MapGet("/concepts/{id:guid}/masks", (Guid id, GenerationService g) => g.MasksOfAsync(id));

        // Manifest, programs, builds
        api.MapGet("/assets/{id:guid}/manifest", async (Guid id, SlopolyDb db) => await db.Manifests.FindAsync(id) is { } m ? Results.Ok(m) : Results.NoContent());
        api.MapPut("/assets/{id:guid}/manifest", (Guid id, JsonObject content, StudioService s) => s.SaveManifestAsync(id, content));
        api.MapGet("/assets/{id:guid}/programs", (Guid id, SlopolyDb db) => db.ProgramVersions.Where(v => v.AssetId == id).OrderByDescending(v => v.Number).ToListAsync());
        api.MapPost("/assets/{id:guid}/programs", async (Guid id, ProgramSubmit submit, GenerationService g) =>
        {
            var (version, job) = await g.SubmitProgramAsync(id, submit.Source, submit.Note ?? "");
            return new { version, job };
        });
        api.MapPut("/assets/{id:guid}/current-version", (Guid id, CurrentVersionEdit edit, StudioService s) => s.SetCurrentVersionAsync(id, edit.VersionId));
        api.MapGet("/assets/{id:guid}/builds", (Guid id, SlopolyDb db) => db.Builds.Where(b => b.AssetId == id).OrderByDescending(b => b.CreatedAt).ToListAsync());
        // Export: the GLB (main palette embedded) plus palette_<variant>.png per variant, zipped.
        api.MapGet("/builds/{id:guid}/export", async (Guid id, SlopolyDb db, FileStore files) =>
        {
            var build = await db.Builds.FindAsync(id) ?? throw StudioException.NotFound("Build");
            var asset = await db.Assets.FindAsync(build.AssetId) ?? throw StudioException.NotFound("Asset");
            if (build.GlbFileId is not { } glb) throw new StudioException("The build has no model file.");
            var variants = await db.PaletteVariants.Where(v => v.PackId == asset.PackId && v.TextureFileId != null).ToListAsync();
            var zip = new MemoryStream();
            using (var archive = new ZipArchive(zip, ZipArchiveMode.Create, leaveOpen: true))
            {
                archive.CreateEntryFromFile(files.PathOf(glb), $"{FileName(asset.Name)}.glb");
                foreach (var v in variants) archive.CreateEntryFromFile(files.PathOf(v.TextureFileId!.Value), $"palette_{FileName(v.Name)}.png");
            }
            zip.Position = 0;
            return Results.File(zip, "application/zip", $"{FileName(asset.Name)}.zip");
        });

        // Scenes
        api.MapGet("/packs/{id:guid}/scenes", (Guid id, SlopolyDb db) => db.Scenes.Where(s => s.PackId == id).OrderBy(s => s.Name).ToListAsync());
        api.MapPut("/packs/{id:guid}/scenes", (Guid id, SceneEdit edit, GenerationService g) => g.SaveSceneAsync(id, edit));
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
        api.MapGet("/packs/{id:guid}/jobs", (Guid id, SlopolyDb db) => db.Jobs.Where(j => j.PackId == id).OrderByDescending(j => j.CreatedAt).Take(200).ToListAsync());
        api.MapGet("/jobs", (Guid? packId, Guid? assetId, string? kind, SlopolyDb db) => db.Jobs
            .Where(j => (packId == null || j.PackId == packId) && (assetId == null || j.AssetId == assetId) && (kind == null || j.Kind == kind))
            .OrderByDescending(j => j.CreatedAt).Take(100).ToListAsync());
        api.MapGet("/jobs/{id:guid}", (Guid id, JobService j) => j.GetAsync(id));
        api.MapGet("/jobs/{id:guid}/events", (Guid id, SlopolyDb db) => db.JobEvents.Where(e => e.JobId == id).OrderBy(e => e.Id).ToListAsync());
        api.MapPost("/jobs/{id:guid}/cancel", (Guid id, JobService j) => j.CancelAsync(id));
        api.MapPost("/jobs/{id:guid}/retry", (Guid id, JobService j) => j.RetryAsync(id));
        api.MapPost("/packs/{id:guid}/chat", async (Guid id, ChatMessage message, StudioService s, JobService j) =>
        {
            var pack = await s.GetPackAsync(id);
            if (string.IsNullOrWhiteSpace(message.Message)) throw new StudioException("The message is empty.");
            return await j.SubmitAsync(JobKinds.AgentTurn, null, id, null,
                new JsonObject { ["message"] = message.Message, ["sessionId"] = pack.AgentSessionId });
        });
        api.MapGet("/packs/{id:guid}/chat", async (Guid id, SlopolyDb db) =>
        {
            var turns = await db.Jobs.Where(j => j.PackId == id && j.Kind == JobKinds.AgentTurn).OrderBy(j => j.CreatedAt).ToListAsync();
            var ids = turns.Select(t => t.Id).ToList();
            var events = (await db.JobEvents.Where(e => ids.Contains(e.JobId)).OrderBy(e => e.Id).ToListAsync()).ToLookup(e => e.JobId);
            return turns.Select(t => new ChatTurn(t, events[t.Id].ToList())).ToList();
        });

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

    /// <summary>Maps <see cref="StudioException"/> to problem details.</summary>
    public static void UseStudioErrors(this WebApplication app) =>
        app.Use(async (context, next) =>
        {
            try { await next(context); }
            catch (StudioException ex) when (!context.Response.HasStarted)
            {
                context.Response.StatusCode = ex.Status;
                await context.Response.WriteAsJsonAsync(new ProblemDetails { Status = ex.Status, Title = ex.Message });
            }
        });
}
