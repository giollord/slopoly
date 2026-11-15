using MudBlazor;
using Slopoly.Contracts;
using Slopoly.Web.Components.Shared;

namespace Slopoly.Web.Services;

/// <summary>Sets a concept's selection. Picking a hero for a variant that already has a reference asks the user
/// whether the hero replaces the reference or starts a new variant (the API refuses the pick until they choose).</summary>
public static class HeroPick
{
    /// <summary>Returns the updated concept, or null when the user cancelled.</summary>
    public static async Task<ConceptImage?> SelectAsync(StudioApi api, IDialogService dialogs, ConceptImage concept, Selection selection)
    {
        try
        {
            return await api.PutAsync<ConceptImage>($"api/concepts/{concept.Id}/selection", new SelectionEdit(selection));
        }
        catch (ApiException ex) when (ex.Code == SelectionConflicts.ReferenceExists)
        {
            var choice = await dialogs.ShowMessageBoxAsync("This variant already has a reference hero",
                "Make this hero the variant's reference (the old one stays, unpicked, with its views), or start a new variant from it?",
                yesText: "Replace reference", noText: "New variant", cancelText: "Cancel");
            if (choice is null) return null;
            if (choice == true)
                return await api.PutAsync<ConceptImage>($"api/concepts/{concept.Id}/selection", new SelectionEdit(selection, SelectionConflicts.Replace));
            var name = await NameDialog.AskAsync(dialogs, "New variant", "Variant name", "Create");
            if (name is null) return null;
            return await api.PutAsync<ConceptImage>($"api/concepts/{concept.Id}/selection", new SelectionEdit(selection, SelectionConflicts.NewVariant, name));
        }
    }
}
