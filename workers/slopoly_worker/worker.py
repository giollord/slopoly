"""Consumes job queues, runs handlers, reports events. One job at a time per kind (prefetch 1)."""

from __future__ import annotations

import asyncio
import logging
import os
from collections.abc import Awaitable, Callable
from pathlib import Path
from typing import Any
from uuid import UUID

import aio_pika
import httpx
from aio_pika.abc import AbstractIncomingMessage

from .protocol import (CONTROL_EXCHANGE, EVENTS_EXCHANGE, JOBS_EXCHANGE, ControlMessage, JobMessage, JobState,
                       WorkerEvent, job_queue)

log = logging.getLogger("slopoly_worker")


class JobFailed(Exception):
    """A handler's expected failure: the message is shown to the user and the agent."""

    def __init__(self, message: str, code: str | None = None):
        super().__init__(message)
        self.code = code


class Job:
    """What a handler gets: the job message plus progress/stream reporting and file transfer."""

    def __init__(self, worker: Worker, message: JobMessage):
        self._worker = worker
        self.message = message
        self.id = message.job_id
        self.kind = message.kind
        self.operation = message.operation
        self.inputs = message.inputs

    async def progress(self, fraction: float) -> None:
        await self._worker.publish(self.kind, WorkerEvent(job_id=self.id, type="progress", progress=max(0.0, min(1.0, fraction))))

    async def stream(self, data: dict[str, Any]) -> None:
        await self._worker.publish(self.kind, WorkerEvent(job_id=self.id, type="stream", data=data))

    async def download(self, file_id: str | UUID, target: Path) -> Path:
        target.parent.mkdir(parents=True, exist_ok=True)
        async with self._worker.api.stream("GET", f"/api/files/{file_id}") as response:
            response.raise_for_status()
            with target.open("wb") as out:
                async for chunk in response.aiter_bytes():
                    out.write(chunk)
        return target

    async def read(self, file_id: str | UUID) -> bytes:
        response = await self._worker.api.get(f"/api/files/{file_id}")
        response.raise_for_status()
        return response.content

    async def upload(self, content: bytes | Path, name: str, content_type: str = "application/octet-stream") -> str:
        data = content.read_bytes() if isinstance(content, Path) else content
        response = await self._worker.api.post("/worker/files", files={"file": (name, data, content_type)})
        response.raise_for_status()
        return response.json()["id"]


Handler = Callable[[Job], Awaitable[dict[str, Any]]]


class Worker:
    def __init__(self, handlers: dict[str, Handler], *, amqp_url: str | None = None, api_url: str | None = None,
                 worker_key: str | None = None, max_attempts: int | None = None):
        self.handlers = handlers
        self.amqp_url = amqp_url or os.environ.get("SLOPOLY_AMQP_URL") or os.environ["ConnectionStrings__rabbitmq"]
        self.max_attempts = max_attempts or int(os.environ.get("SLOPOLY_MAX_ATTEMPTS", "3"))
        self.api = httpx.AsyncClient(base_url=api_url or os.environ["SLOPOLY_API_URL"], timeout=120,
                                     headers={"X-Worker-Key": worker_key or os.environ["SLOPOLY_WORKER_KEY"]})
        self._running: dict[UUID, asyncio.Task] = {}
        self._connection: aio_pika.abc.AbstractRobustConnection | None = None
        self._events: aio_pika.abc.AbstractExchange | None = None

    async def start(self) -> None:
        """Connects, declares the topology and starts consuming; returns once consumers are registered."""
        self._connection = await aio_pika.connect_robust(self.amqp_url)
        publish_channel = await self._connection.channel()
        self._events = await publish_channel.declare_exchange(EVENTS_EXCHANGE, aio_pika.ExchangeType.TOPIC, durable=True)
        await publish_channel.declare_exchange(JOBS_EXCHANGE, aio_pika.ExchangeType.DIRECT, durable=True)

        control_channel = await self._connection.channel()
        control = await control_channel.declare_exchange(CONTROL_EXCHANGE, aio_pika.ExchangeType.FANOUT, durable=True)
        control_queue = await control_channel.declare_queue(exclusive=True, auto_delete=True)
        await control_queue.bind(control)
        await control_queue.consume(self._on_control, no_ack=True)

        for kind in self.handlers:
            channel = await self._connection.channel()
            await channel.set_qos(prefetch_count=1)
            jobs = await channel.declare_exchange(JOBS_EXCHANGE, aio_pika.ExchangeType.DIRECT, durable=True)
            queue = await channel.declare_queue(job_queue(kind), durable=True)
            await queue.bind(jobs, routing_key=kind)
            await queue.consume(self._on_job)
        log.info("Worker consuming %s", ", ".join(self.handlers))

    async def run(self) -> None:
        await self.start()
        await asyncio.Future()

    async def close(self) -> None:
        for task in self._running.values():
            task.cancel()
        if self._connection:
            await self._connection.close()
        await self.api.aclose()

    async def publish(self, kind: str, event: WorkerEvent) -> None:
        assert self._events is not None
        await self._events.publish(
            aio_pika.Message(event.dump(), content_type="application/json", delivery_mode=aio_pika.DeliveryMode.PERSISTENT),
            routing_key=f"{kind}.{event.type}")

    async def _on_control(self, message: AbstractIncomingMessage) -> None:
        try:
            control = ControlMessage.model_validate_json(message.body)
        except ValueError:
            return
        if task := self._running.get(control.job_id):
            log.info("Job %s cancelled", control.job_id)
            task.cancel()

    async def _job_state(self, job_id: UUID) -> JobState:
        response = await self.api.get(f"/worker/jobs/{job_id}")
        response.raise_for_status()
        return JobState.model_validate(response.json())

    async def _on_job(self, message: AbstractIncomingMessage) -> None:
        try:
            job = JobMessage.model_validate_json(message.body)
        except ValueError:
            log.exception("Malformed job message dropped")
            await message.ack()
            return
        try:
            await self._process(job, message.redelivered)
        except Exception:
            # The API is unreachable or similar: give the job back so it isn't lost.
            log.exception("Job %s could not be processed; requeued", job.job_id)
            await asyncio.sleep(2)
            await message.nack(requeue=True)
            return
        await message.ack()

    async def _process(self, job: JobMessage, redelivered: bool) -> None:
        state = await self._job_state(job.job_id)
        if state.state in ("Cancelled", "Succeeded", "Failed"):
            log.info("Job %s is %s; skipped", job.job_id, state.state.lower())
            return
        if redelivered and state.attempt >= self.max_attempts:
            await self.publish(job.kind, WorkerEvent(job_id=job.job_id, type="failed", error_code="attempts_exhausted",
                                                     error=f"The job was interrupted {state.attempt} times and was given up."))
            return

        handler = self.handlers[job.kind]
        await self.publish(job.kind, WorkerEvent(job_id=job.job_id, type="started"))
        task = asyncio.create_task(handler(Job(self, job)))
        self._running[job.job_id] = task
        try:
            outputs = await task
        except asyncio.CancelledError:
            if not task.cancelled():
                raise  # the worker itself is shutting down; the broker redelivers the unacked job
            return  # cancelled by the user; the API already recorded it
        except JobFailed as failure:
            await self.publish(job.kind, WorkerEvent(job_id=job.job_id, type="failed", error=str(failure), error_code=failure.code))
            return
        except Exception as error:
            log.exception("Job %s failed", job.job_id)
            await self.publish(job.kind, WorkerEvent(job_id=job.job_id, type="failed", error=f"{type(error).__name__}: {error}"))
            return
        finally:
            self._running.pop(job.job_id, None)
        await self.publish(job.kind, WorkerEvent(job_id=job.job_id, type="succeeded", outputs=outputs or {}))


def run(handlers: dict[str, Handler]) -> None:
    """Entry point for a worker container."""
    logging.basicConfig(level=os.environ.get("LOG_LEVEL", "INFO"), format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    asyncio.run(Worker(handlers).run())
