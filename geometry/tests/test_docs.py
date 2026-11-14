"""The agent's API reference documents every public program name."""
import re
from pathlib import Path

import slopoly_model as sm

DOC = Path(__file__).resolve().parents[2] / "agent" / "docs" / "slopoly_model.md"


def test_every_public_name_is_documented():
    text = DOC.read_text(encoding="utf-8")
    documented = set(re.findall(r"`([A-Za-z_]\w*)\(", text)) | set(re.findall(r"`(\w+)`", text))
    missing = [name for name in sm.__all__ if name not in documented]
    assert not missing, f"undocumented in {DOC.name}: {missing}"


KNOWLEDGE = Path(__file__).resolve().parents[2] / "knowledge"


def test_knowledge_note_examples_run():
    from slopoly_model.runner import run_program

    blocks = [(note.name, block) for note in sorted(KNOWLEDGE.glob("*.md"))
              for block in re.findall(r"```python\n(.*?)```", note.read_text(encoding="utf-8"), re.S)]
    assert blocks, f"no examples in {KNOWLEDGE}"
    for name, block in blocks:
        run_program(block)  # raises ProgramError with the line on failure
