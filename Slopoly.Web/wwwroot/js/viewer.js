// Small helpers called from Blazor: keep a chat scrolled to its newest message, and per-browser settings (the
// viewer's overlay choices). Storage can be unavailable (private windows, blocked site data): reads then return null.
window.slopolyViewer = {
    scrollToEnd(element) { if (element) element.scrollTop = element.scrollHeight; },
    load(key) {
        try { const value = localStorage.getItem(key); return value ? JSON.parse(value) : null; } catch { return null; }
    },
    save(key, value) {
        try { localStorage.setItem(key, JSON.stringify(value)); } catch { /* not kept */ }
    }
};
