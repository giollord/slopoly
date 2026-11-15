using MudBlazor.Services;
using Slopoly.Web.Components;
using Slopoly.Web.Services;

var builder = WebApplication.CreateBuilder(args);

builder.AddServiceDefaults();

builder.Services.AddRazorComponents().AddInteractiveServerComponents();
builder.Services.AddMudServices();
builder.Services.AddHttpClient<StudioApi>(client => client.BaseAddress = new("https+http://apiservice"));
builder.Services.AddSingleton<LiveEvents>();
builder.Services.AddScoped<PageContext>();
builder.Services.AddHostedService(sp => sp.GetRequiredService<LiveEvents>());

var app = builder.Build();

if (!app.Environment.IsDevelopment())
{
    app.UseExceptionHandler("/Error", createScopeForErrors: true);
    app.UseHsts();
}

app.UseHttpsRedirection();
app.UseAntiforgery();
app.MapStaticAssets();

// The browser loads images, models and exports through the web app; the API stays internal.
app.MapGet("/files/{id:guid}", (Guid id, StudioApi api, HttpContext context) => api.ForwardAsync($"api/files/{id}", context));
app.MapGet("/builds/{id:guid}/export", (Guid id, StudioApi api, HttpContext context) => api.ForwardAsync($"api/builds/{id}/export", context));
app.MapGet("/builds/{id:guid}/blend", (Guid id, StudioApi api, HttpContext context) => api.ForwardAsync($"api/builds/{id}/blend", context));

app.MapRazorComponents<App>().AddInteractiveServerRenderMode();
app.MapDefaultEndpoints();

app.Run();
