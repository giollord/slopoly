using System.Net;
using System.Net.Http.Json;
using System.Text.Json;
using System.Text.Json.Serialization;
using Microsoft.AspNetCore.Mvc;

namespace Slopoly.Web.Services;

/// <summary>An API call failed; the message is the API's problem title, fit to show to the user. Code names a
/// specific refusal (e.g. "reference_exists").</summary>
public sealed class ApiException(string message, string? code = null) : Exception(message)
{
    public string? Code { get; } = code;
}

/// <summary>Typed access to the Slopoly API (service discovery name "apiservice").</summary>
public sealed class StudioApi(HttpClient http)
{
    public static readonly JsonSerializerOptions Json = new(JsonSerializerDefaults.Web) { Converters = { new JsonStringEnumConverter() } };

    public async Task<T> GetAsync<T>(string url) => await ReadAsync<T>(await http.GetAsync(url));

    /// <summary>GET that returns default for 204 No Content.</summary>
    public async Task<T?> FindAsync<T>(string url)
    {
        var response = await http.GetAsync(url);
        return response.StatusCode == HttpStatusCode.NoContent ? default : await ReadAsync<T>(response);
    }

    public async Task<T> PostAsync<T>(string url, object? body = null) => await ReadAsync<T>(await http.PostAsJsonAsync(url, body, Json));
    public async Task<T> PutAsync<T>(string url, object body) => await ReadAsync<T>(await http.PutAsJsonAsync(url, body, Json));
    public async Task<T> PatchAsync<T>(string url, object body) => await ReadAsync<T>(await http.PatchAsJsonAsync(url, body, Json));
    public async Task DeleteAsync(string url) => await EnsureAsync(await http.DeleteAsync(url));

    public async Task<T> UploadAsync<T>(string url, Stream content, string name, string contentType)
    {
        using var form = new MultipartFormDataContent();
        var file = new StreamContent(content);
        file.Headers.ContentType = new(contentType);
        form.Add(file, "file", name);
        return await ReadAsync<T>(await http.PostAsync(url, form));
    }

    /// <summary>Streams an API GET response (files, exports) to the browser.</summary>
    public async Task ForwardAsync(string url, HttpContext context)
    {
        using var response = await http.GetAsync(url, HttpCompletionOption.ResponseHeadersRead, context.RequestAborted);
        context.Response.StatusCode = (int)response.StatusCode;
        foreach (var header in response.Content.Headers.Where(h => h.Key is "Content-Type" or "Content-Disposition" or "Content-Length"))
            context.Response.Headers[header.Key] = header.Value.ToArray();
        if (response.IsSuccessStatusCode && url.StartsWith("api/files/"))
            context.Response.Headers.CacheControl = "private, max-age=31536000, immutable"; // a file id never changes content
        await response.Content.CopyToAsync(context.Response.Body, context.RequestAborted);
    }

    private static async Task<T> ReadAsync<T>(HttpResponseMessage response)
    {
        await EnsureAsync(response);
        return (await response.Content.ReadFromJsonAsync<T>(Json))!;
    }

    private static async Task EnsureAsync(HttpResponseMessage response)
    {
        if (response.IsSuccessStatusCode) return;
        string? title = null, code = null;
        try
        {
            var problem = await response.Content.ReadFromJsonAsync<ProblemDetails>(Json);
            title = problem?.Title;
            code = problem?.Extensions.TryGetValue("code", out var value) == true ? value?.ToString() : null;
        }
        catch (JsonException) { }
        throw new ApiException(title ?? $"The API answered {(int)response.StatusCode} {response.ReasonPhrase}.", code);
    }
}
