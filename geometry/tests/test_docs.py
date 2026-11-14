"""The agent's API reference documents every public program name, and every shipped sample builds."""
import re
from pathlib import Path

import pytest

import slopoly_model as sm

DOC = Path(__file__).resolve().parents[2] / "agent" / "docs" / "slopoly_model.md"
KNOWLEDGE = Path(__file__).resolve().parents[2] / "knowledge"
SAMPLE_TRIANGLES = 3000  # a sample over this is not a low-poly example
CODE = re.compile(r"```python\n(.*?)```", re.S)


def test_every_public_name_is_documented():
    text = DOC.read_text(encoding="utf-8")
    documented = set(re.findall(r"`([A-Za-z_]\w*)\(", text)) | set(re.findall(r"`(\w+)`", text))
    missing = [name for name in sm.__all__ if name not in documented]
    assert not missing, f"undocumented in {DOC.name}: {missing}"


def check_samples(folder: Path) -> int:
    """Builds every Python block of every note under ``folder``; raises AssertionError naming the note."""
    from slopoly_model import assembly
    from slopoly_model.runner import ProgramError, run_program

    count = 0
    for note in sorted(folder.rglob("*.md")):
        name = note.relative_to(folder).as_posix()
        for block in CODE.findall(note.read_text(encoding="utf-8")):
            try:
                model = run_program(block)
            except ProgramError as error:
                raise AssertionError(f"{name}: sample fails at line {error.line}: {error}") from None
            triangles = sum(p.shape.triangle_count() for p in model.parts.values())
            assert triangles <= SAMPLE_TRIANGLES, f"{name}: sample uses {triangles} triangles"
            assembly.new_model()
            count += 1
    return count


def test_knowledge_note_examples_run():
    assert check_samples(KNOWLEDGE), f"no examples in {KNOWLEDGE}"


def test_a_broken_sample_names_its_note(tmp_path):
    (tmp_path / "techniques").mkdir()
    (tmp_path / "techniques" / "broken.md").write_text("---\ntitle: Broken\n---\n\n```python\nbox(1, 1)\n```\n")
    with pytest.raises(AssertionError, match="techniques/broken.md: sample fails at line 1"):
        check_samples(tmp_path)


def test_reference_example_runs():
    from slopoly_model.runner import run_program

    blocks = CODE.findall(DOC.read_text(encoding="utf-8"))
    assert blocks
    for block in blocks:
        run_program(block)
