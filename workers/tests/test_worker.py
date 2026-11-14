"""slopoly_worker against a real RabbitMQ (compose service) and a mocked API."""

import asyncio
import json
import os
import uuid

import aio_pika
import httpx
import pytest
import respx

from slopoly_worker import Job, JobFailed, Worker
from slopoly_worker.protocol import CONTROL_EXCHANGE, EVENTS_EXCHANGE, JOBS_EXCHANGE, ControlMessage, JobMessage, job_queue

AMQP = os.environ.get("SLOPOLY_TEST_AMQP_URL", "amqp://guest:guest@localhost:5672/")
API = "http://api.test"


class Harness:
    """Plays the API: job states over HTTP, job dispatch and event collection over AMQP."""

    def __init__(self):
        self.kind = f"test-{uuid.uuid4().hex[:8]}"
        self.states: dict[str, dict] = {}
        self.events: list[dict] = []
        self.uploads: list[str] = []

    async def __aenter__(self):
        self.connection = await aio_pika.connect_robust(AMQP)
        self.channel = await self.connection.channel()
        events = await self.channel.declare_exchange(EVENTS_EXCHANGE, aio_pika.ExchangeType.TOPIC, durable=True)
        queue = await self.channel.declare_queue(exclusive=True)
        await queue.bind(events, routing_key=f"{self.kind}.#")
        await queue.consume(self._on_event, no_ack=True)
        self.jobs = await self.channel.declare_exchange(JOBS_EXCHANGE, aio_pika.ExchangeType.DIRECT, durable=True)
        self.control = await self.channel.declare_exchange(CONTROL_EXCHANGE, aio_pika.ExchangeType.FANOUT, durable=True)
        self.mock = respx.mock(base_url=API, assert_all_called=False)
        self.mock.start()
        self.mock.get(path__regex=r"/worker/jobs/(?P<job_id>[^/]+)").mock(side_effect=self._state)
        self.mock.post("/worker/files").mock(side_effect=self._upload)
        return self

    async def __aexit__(self, *_):
        self.mock.stop()
        await self.connection.close()

    def worker(self, handler) -> Worker:
        return Worker({self.kind: handler}, amqp_url=AMQP, api_url=API, worker_key="k", max_attempts=3)

    async def _on_event(self, message):
        self.events.append(json.loads(message.body))

    def _state(self, request, job_id):
        return httpx.Response(200, json=self.states.get(job_id, {"id": job_id, "state": "Queued", "attempt": 0}))

    def _upload(self, request):
        file_id = str(uuid.uuid4())
        self.uploads.append(file_id)
        return httpx.Response(200, json={"id": file_id})

    async def dispatch(self, inputs=None) -> str:
        job_id = str(uuid.uuid4())
        message = JobMessage(job_id=job_id, kind=self.kind, inputs=inputs or {})
        await self.jobs.publish(aio_pika.Message(message.dump(), delivery_mode=aio_pika.DeliveryMode.PERSISTENT), routing_key=self.kind)
        return job_id

    async def cancel(self, job_id: str):
        await self.control.publish(aio_pika.Message(ControlMessage(type="cancel", job_id=job_id).dump()), routing_key="")

    def types(self, job_id: str) -> list[str]:
        return [e["type"] for e in self.events if e["jobId"] == job_id]

    async def wait_for(self, job_id: str, event_type: str, timeout=10.0):
        async def poll():
            while event_type not in self.types(job_id):
                await asyncio.sleep(0.05)
        await asyncio.wait_for(poll(), timeout)

    async def queue_depth(self) -> int:
        queue = await self.channel.declare_queue(job_queue(self.kind), durable=True, passive=True)
        return queue.declaration_result.message_count


async def test_job_runs_and_reports_outputs():
    async with Harness() as h:
        async def handler(job: Job):
            await job.progress(0.5)
            await job.stream({"text": "working"})
            file_id = await job.upload(b"png", "out.png", "image/png")
            return {"fileId": file_id, "echo": job.inputs["x"]}

        worker = h.worker(handler)
        await worker.start()
        job_id = await h.dispatch({"x": 42})
        await h.wait_for(job_id, "succeeded")
        await worker.close()

        assert h.types(job_id) == ["started", "progress", "stream", "succeeded"]
        succeeded = next(e for e in h.events if e["type"] == "succeeded")
        assert succeeded["outputs"] == {"fileId": h.uploads[0], "echo": 42}


async def test_handler_failure_is_reported():
    async with Harness() as h:
        async def handler(job: Job):
            raise JobFailed("Missing model: flux.safetensors", "missing_model")

        worker = h.worker(handler)
        await worker.start()
        job_id = await h.dispatch()
        await h.wait_for(job_id, "failed")
        await worker.close()
        failed = next(e for e in h.events if e["type"] == "failed")
        assert failed["error"] == "Missing model: flux.safetensors" and failed["errorCode"] == "missing_model"


async def test_cancel_mid_run_stops_handler_and_acks():
    async with Harness() as h:
        started = asyncio.Event()
        finished = False

        async def handler(job: Job):
            nonlocal finished
            started.set()
            await asyncio.sleep(30)
            finished = True
            return {}

        worker = h.worker(handler)
        await worker.start()
        job_id = await h.dispatch()
        await asyncio.wait_for(started.wait(), 10)
        h.states[job_id] = {"id": job_id, "state": "Cancelled", "attempt": 1}
        await h.cancel(job_id)
        await asyncio.sleep(1)
        await worker.close()

        assert not finished
        assert h.types(job_id) == ["started"]
        assert await h.queue_depth() == 0


async def test_cancelled_before_start_is_skipped():
    async with Harness() as h:
        calls = 0

        async def handler(job: Job):
            nonlocal calls
            calls += 1
            return {}

        job_id = await h.dispatch()
        h.states[job_id] = {"id": job_id, "state": "Cancelled", "attempt": 0}
        worker = h.worker(handler)
        await worker.start()
        await asyncio.sleep(1)
        await worker.close()

        assert calls == 0 and h.types(job_id) == []
        assert await h.queue_depth() == 0


async def test_unacked_job_is_redelivered_after_worker_loss():
    async with Harness() as h:
        first_started = asyncio.Event()

        async def hang(job: Job):
            first_started.set()
            await asyncio.sleep(60)
            return {}

        async def finish(job: Job):
            return {"ok": True}

        crashed = h.worker(hang)
        await crashed.start()
        job_id = await h.dispatch()
        await asyncio.wait_for(first_started.wait(), 10)
        h.states[job_id] = {"id": job_id, "state": "Running", "attempt": 1}
        await crashed._connection.close()  # connection drops without ack

        survivor = h.worker(finish)
        await survivor.start()
        await h.wait_for(job_id, "succeeded")
        await survivor.close()
        await crashed.close()
        assert h.types(job_id) == ["started", "started", "succeeded"]


async def test_redelivered_job_gives_up_after_max_attempts():
    async with Harness() as h:
        started = asyncio.Event()

        async def hang(job: Job):
            started.set()
            await asyncio.sleep(60)
            return {}

        crashed = h.worker(hang)
        await crashed.start()
        job_id = await h.dispatch()
        await asyncio.wait_for(started.wait(), 10)
        h.states[job_id] = {"id": job_id, "state": "Running", "attempt": 3}
        await crashed._connection.close()

        survivor = h.worker(hang)
        await survivor.start()
        await h.wait_for(job_id, "failed")
        await survivor.close()
        await crashed.close()
        failed = [e for e in h.events if e["type"] == "failed"][0]
        assert failed["errorCode"] == "attempts_exhausted"
