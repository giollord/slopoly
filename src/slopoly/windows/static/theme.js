// Light or dark theme for the window pages, switched by a button and kept in the prefs (auto follows the system).
const NAMES = ["auto", "light", "dark"];

function apply(theme) {
    if (theme === "light" || theme === "dark") document.documentElement.dataset.theme = theme;
    else delete document.documentElement.dataset.theme;
}

export async function themeSwitch(button) {
    const prefs = await fetch("api/prefs").then(r => r.json()).catch(() => ({}));
    let theme = NAMES.includes(prefs.theme) ? prefs.theme : "auto";
    const show = () => { apply(theme); button.textContent = `Theme: ${theme}`; };
    button.title = "Switch between the system's theme, light and dark";
    button.onclick = async () => {
        theme = NAMES[(NAMES.indexOf(theme) + 1) % NAMES.length];
        show();
        const current = await fetch("api/prefs").then(r => r.json()).catch(() => ({}));
        fetch("api/prefs", { method: "POST", headers: { "Content-Type": "application/json" },
                             body: JSON.stringify({ ...current, theme }) });
    };
    show();
}
