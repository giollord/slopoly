"""The CLI, the plugin and the marketplace entry carry one version."""

import json
import re
import tomllib
from pathlib import Path

ROOT = Path(__file__).parent.parent
VERSION = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))["project"]["version"]


def test_plugin_manifest():
    assert json.loads((ROOT / "plugin/.claude-plugin/plugin.json").read_text(encoding="utf-8"))["version"] == VERSION


def test_marketplace_entry():
    market = json.loads((ROOT / ".claude-plugin/marketplace.json").read_text(encoding="utf-8"))
    assert market["metadata"]["version"] == VERSION
    assert [p["version"] for p in market["plugins"] if p["name"] == "slopoly"] == [VERSION]


def test_skill_requires_this_version():
    skill = (ROOT / "plugin/skills/slopoly/SKILL.md").read_text(encoding="utf-8")
    assert re.search(r"slopoly CLI version (\S+?)\.?\s", skill).group(1) == VERSION


def test_skill_installs_this_version():
    skill = (ROOT / "plugin/skills/slopoly/SKILL.md").read_text(encoding="utf-8")
    assert f"@v{VERSION}" in skill


def test_references_exist_and_avoid_old_tool_names():
    folder = ROOT / "plugin/skills/slopoly"
    skill = (folder / "SKILL.md").read_text(encoding="utf-8")
    for ref in re.findall(r"`(references/[\w./-]+)`", skill):
        assert (folder / ref).exists(), ref
    for path in folder.rglob("*.md"):
        text = path.read_text(encoding="utf-8")
        for old in ("MCP", "submit_program", "get_build_report", "search_knowledge", "view_image", "upsert_palette"):
            assert old not in text, f"{path.name} mentions {old}"
