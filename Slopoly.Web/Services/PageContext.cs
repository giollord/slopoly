using Slopoly.Contracts;

namespace Slopoly.Web.Services;

/// <summary>
/// What the user is looking at (per circuit): pages publish their <see cref="ChatContext"/>, and chats use it for a new
/// chat's context and for the page line of each message. Pages can also ask the layout to open the chat drawer.
/// </summary>
public sealed class PageContext
{
    public ChatContext Current { get; private set; } = new(ChatPages.Home);

    /// <summary>The page's context changed.</summary>
    public event Action? Changed;

    /// <summary>A page asks the layout to open the chat drawer (optionally on a given chat).</summary>
    public event Action<Guid?>? OpenChatRequested;

    public void Set(ChatContext context)
    {
        if (context == Current) return;
        Current = context;
        Changed?.Invoke();
    }

    public void OpenChat(Guid? chatId = null) => OpenChatRequested?.Invoke(chatId);
}
