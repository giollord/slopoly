"""Message contract shared with the API (Slopoly.ApiService/Jobs/Broker.cs). Keep both sides in sync."""

from __future__ import annotations

from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict
from pydantic.alias_generators import to_camel

JOBS_EXCHANGE = "jobs"  # direct, routing key = kind
EVENTS_EXCHANGE = "job-events"  # topic, routing key = <kind>.<type>
CONTROL_EXCHANGE = "job-control"  # fanout
KINDS = ("comfy", "build", "palette-render", "agent-turn")


def job_queue(kind: str) -> str:
    return f"jobs.{kind}"


class Message(BaseModel):
    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)

    def dump(self) -> bytes:
        return self.model_dump_json(by_alias=True).encode()


class JobMessage(Message):
    job_id: UUID
    kind: str
    operation: str | None = None
    pack_id: UUID | None = None
    asset_id: UUID | None = None
    inputs: dict[str, Any] = {}


class ControlMessage(Message):
    type: Literal["cancel"]
    job_id: UUID


EventType = Literal["started", "progress", "stream", "succeeded", "failed"]


class WorkerEvent(Message):
    job_id: UUID
    type: EventType
    progress: float | None = None
    data: dict[str, Any] | None = None
    outputs: dict[str, Any] | None = None
    error: str | None = None
    error_code: str | None = None


class JobState(Message):
    """The part of the API's job record a worker reads (GET /worker/jobs/{id})."""

    id: UUID
    state: Literal["Queued", "Running", "Succeeded", "Failed", "Cancelled"]
    attempt: int = 0
