"""Errors, JSON output and atomic file writes shared by every command."""

from __future__ import annotations

import json
import os
import sys
import tempfile
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


def write_atomic(path: Path, data: bytes | str) -> None:
    """Writes via a temporary file in the same folder, so readers never see a half-written file."""
    path.parent.mkdir(parents=True, exist_ok=True)
    raw = data.encode("utf-8") if isinstance(data, str) else data
    fd, tmp = tempfile.mkstemp(dir=path.parent, prefix=f".{path.name}.", suffix=".tmp")
    try:
        with os.fdopen(fd, "wb") as out:
            out.write(raw)
        os.replace(tmp, path)
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
        raise invalid_file(path, problems_of(error)) from error
