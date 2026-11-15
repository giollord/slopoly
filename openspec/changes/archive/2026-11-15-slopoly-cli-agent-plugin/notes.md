# Notes

## Marketplace spike (task 1.1), 2026-11-15

Source: GitHub Docs, "GitHub Copilot CLI plugin reference" (docs.github.com/en/copilot/reference/copilot-cli-reference/cli-plugin-reference)
and "Creating a plugin marketplace for GitHub Copilot CLI".

- Copilot CLI looks for a marketplace manifest at, in order: `marketplace.json`, `.plugin/marketplace.json`,
  `.github/plugin/marketplace.json`, `.claude-plugin/marketplace.json`. Required fields: `name`, `owner {name}`,
  `plugins[] {name, source}`. `source` may be a relative path (`./plugin`).
- Plugin manifest (legacy format, which Claude Code also uses): `.plugin/plugin.json`, `plugin.json`,
  `.github/plugin/plugin.json` or `.claude-plugin/plugin.json`, with `name` required. Skills are loaded from `skills/`
  (immediate subfolders with a `SKILL.md`) by default.
- Adding: `copilot plugin marketplace add OWNER/REPO`, then `copilot plugin install slopoly@<marketplace-name>`.
  Claude Code: `/plugin marketplace add OWNER/REPO`, then `/plugin install slopoly@<marketplace-name>`.

**Outcome:** a single `.claude-plugin/marketplace.json` at the repository root plus `plugin/.claude-plugin/plugin.json`
serves both agents. No second manifest is needed, so design decision 9 holds as written (its "if" resolves to "reads
`.claude-plugin/marketplace.json`").

Copilot CLI is not installed on the development machine, so the install check (task 7.3) can only run in Claude Code
here.

## Plugin install check (task 7.3), 2026-11-15

- `claude plugin validate .` passes (marketplace and plugin manifests).
- A headless Claude Code session started with `--plugin-dir ./plugin` lists the skill `slopoly:slopoly`.
- Bootstrap, run by hand: `uv tool install --force .` (the skill's `git+https://github.com/giollord/slopoly@v0.1.0`
  needs that tag pushed first), then `slopoly --version` printed 0.1.0, and `slopoly doctor` passed against the
  development ComfyUI and Blender 5.3. A build with the installed tool worked, so the package data is in the wheel.
- Not done: GitHub Copilot CLI is not installed here. Adding the marketplace there
  (`copilot plugin marketplace add giollord/slopoly`) is still to be tried.
