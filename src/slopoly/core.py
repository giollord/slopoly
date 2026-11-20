"""Errors, JSON output and atomic file writes shared by every command."""

from __future__ import annotations

import json
import os
import sys
import tempfile
import time
from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, ValidationError


class SlopolyError(Exception):
    """An expected failure: printed as a JSON error with exit status 1 (2 for a failing part program)."""

    def __init__(self, code: str, message: str, hint: str | None = None, status: int = 1, **details: Any):
        super().__init__(message)
        self.code, self.message, self.hint, self.status, self.details = code, message, hint, status, details

    def as_dict(self) -> dict:
        out = {"error": self.message, "code": self.code}
        if self.hint:
            out["hint"] = self.hint
        return out | self.details


def jsonable(value: Any) -> Any:
    if isinstance(value, BaseModel):
        return value.model_dump(mode="json", exclude_none=True)
    if isinstance(value, Path):
        return value.as_posix()
    if isinstance(value, dict):
        return {k: jsonable(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [jsonable(v) for v in value]
    return value


def emit(value: Any) -> None:
    sys.stdout.write(json.dumps(jsonable(value), indent=2, ensure_ascii=False) + "\n")
    sys.stdout.flush()


REPLACE_TRIES = 20  # Windows denies a replace while another process has the file open (e.g. slopoly wait reading it)


def replace(source: str | Path, target: Path) -> None:
    """``os.replace`` that retries briefly while Windows denies it because a reader has the target open."""
    for attempt in range(REPLACE_TRIES):
        try:
            os.replace(source, target)
            return
        except PermissionError:
            if sys.platform != "win32" or attempt == REPLACE_TRIES - 1:
                raise
            time.sleep(0.05 * (attempt + 1))


def write_atomic(path: Path, data: bytes | str) -> None:
    """Writes via a temporary file in the same folder, so readers never see a half-written file."""
    path.parent.mkdir(parents=True, exist_ok=True)
    raw = data.encode("utf-8") if isinstance(data, str) else data
    fd, tmp = tempfile.mkstemp(dir=path.parent, prefix=f".{path.name}.", suffix=".tmp")
    try:
        with os.fdopen(fd, "wb") as out:
            out.write(raw)
        replace(tmp, path)
    except BaseException:
        Path(tmp).unlink(missing_ok=True)
        raise


def dump_yaml(value: Any) -> str:
    return yaml.safe_dump(jsonable(value), sort_keys=False, allow_unicode=True, width=120)


def write_yaml(path: Path, value: Any) -> None:
    write_atomic(path, dump_yaml(value))


def read_yaml(path: Path) -> Any:
    try:
        return yaml.safe_load(path.read_text(encoding="utf-8"))
    except yaml.YAMLError as error:
        raise invalid_file(path, [{"field": "", "message": f"not valid YAML: {error}"}]) from error


def problems_of(error: ValidationError) -> list[dict]:
    return [{"field": ".".join(str(p) for p in e["loc"]), "message": e["msg"]} for e in error.errors()]


def invalid_file(path: Path, problems: list[dict]) -> SlopolyError:
    return SlopolyError("invalid_file", f"{path.as_posix()} is not valid", "fix the listed fields, then run slopoly check",
                        problems=[{"file": path.as_posix()} | p for p in problems])


VERSION_FILE = ".slopoly-version"  # in the workspace root: the newest CLI version that used the workspace


def version_key(text: str) -> tuple[int, ...]:
    return tuple(int(part) for part in text.strip().split(".")[:3] if part.isdigit())


def recorded_version(path: Path) -> str | None:
    """The newest CLI version that used the workspace holding ``path``."""
    for folder in path.resolve().parents:
        marker = folder / VERSION_FILE
        if marker.is_file():
            return marker.read_text(encoding="utf-8").strip() or None
    return None


def record_version(root: Path) -> None:
    """Records this CLI's version in the workspace when it is newer than the one recorded."""
    from . import __version__
    marker = root / VERSION_FILE
    current = marker.read_text(encoding="utf-8").strip() if marker.is_file() else ""
    if not current or version_key(__version__) > version_key(current):
        try:
            write_atomic(marker, __version__ + "\n")
        except OSError:
            pass  # a read-only workspace still works


def newer_version_error(path: Path, error: ValidationError) -> SlopolyError | None:
    """A file with fields this CLI doesn't know, in a workspace used by a newer CLI: a version mismatch."""
    from . import __version__
    if not any(e["type"] == "extra_forbidden" for e in error.errors()):
        return None
    recorded = recorded_version(path)
    if not recorded or version_key(recorded) <= version_key(__version__):
        return None
    return SlopolyError("version_mismatch", f"{path.as_posix()} was written by slopoly {recorded}, newer than this "
                        f"slopoly {__version__}", f"install slopoly {recorded} or newer, then run the command again",
                        workspace_version=recorded, cli_version=__version__)


def load(model: type[BaseModel], path: Path, default: Any = None):
    """Reads and validates a YAML file; a missing file gives ``default`` (or an empty model when default is None)."""
    if not path.exists():
        if default is not None:
            return default
        raise SlopolyError("not_found", f"{path.as_posix()} does not exist")
    data = read_yaml(path)
    try:
        return model.model_validate(data if data is not None else {})
    except ValidationError as error:
        raise newer_version_error(path, error) or invalid_file(path, problems_of(error)) from error
