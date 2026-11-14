# slopoly_worker

The shared job worker installed in every Slopoly worker container (`containers/comfyui`, `containers/geometry`,
`containers/agent`). It consumes jobs from RabbitMQ, runs a handler per job kind, and reports events back. Files never
travel through the broker: handlers download inputs and upload outputs over the API's HTTP endpoints.

## Message contract

The API side is `Slopoly.ApiService/Jobs/Broker.cs`; `slopoly_worker/protocol.py` mirrors it. JSON is camelCase.

| Exchange | Type | Routing key | Messages |
|---|---|---|---|
| `jobs` | direct | job kind | `{jobId, kind, operation, packId, assetId, inputs}` into the durable queue `jobs.<kind>` |
| `job-events` | topic | `<kind>.<type>` | `{jobId, type, progress?, data?, outputs?, error?, errorCode?}`, consumed by the API (`api.job-events`) |
| `job-control` | fanout | — | `{type: "cancel", jobId}`; every worker listens with its own exclusive queue |

Kinds: `comfy`, `build`, `palette-render`, `agent-turn`.

Event types, in order:

- `started`: the worker begins the job. The API counts an attempt per `started`.
- `progress`: `progress` is 0..1. It is broadcast to the UI but not stored.
- `stream`: free-form `data`, such as agent chat output. It is stored as job history.
- `succeeded`: `outputs` is the job result. Its shape is per kind; see `Slopoly.ApiService/Jobs/ResultHandlers.cs`.
- `failed`: `error` is a human-readable message, and `errorCode` is optional (for example `missing_model`, `auth`,
  `attempts_exhausted`).

Delivery rules:

- Each kind is consumed with **prefetch 1** and **manual acks**. The worker acknowledges only after it publishes the
  final event. A worker that dies mid-job leaves the message unacknowledged, and RabbitMQ redelivers it.
- Before running a job, the worker reads `GET /worker/jobs/{id}`:
  - a job that is already cancelled or finished is acknowledged and skipped;
  - a *redelivered* job whose attempt count reached `SLOPOLY_MAX_ATTEMPTS` (default 3) is failed with
    `attempts_exhausted`.
- A `cancel` control message cancels the running handler task. No final event is sent, because the API already marked
  the job cancelled and ignores late results.

## Configuration

| Variable | Meaning |
|---|---|
| `SLOPOLY_AMQP_URL` | RabbitMQ connection string (Aspire passes the broker's) |
| `SLOPOLY_API_URL` | API base URL |
| `SLOPOLY_WORKER_KEY` | Sent as `X-Worker-Key` for `/worker/*` endpoints |
| `SLOPOLY_MAX_ATTEMPTS` | Deliveries before giving up (default 3) |

## Adding a handler

A handler receives a `Job` and returns the `outputs` dict. Raise `JobFailed` for expected failures.

```python
from slopoly_worker import Job, JobFailed, run


async def invert(job: Job) -> dict:
    """Example: inverts an uploaded file's bytes."""
    if "file" not in job.inputs:
        raise JobFailed("No input file given.", "bad_input")
    data = await job.read(job.inputs["file"])
    await job.progress(0.5)
    file_id = await job.upload(bytes(255 - b for b in data), "inverted.bin")
    return {"fileId": file_id}


if __name__ == "__main__":
    run({"example": invert})
```

`Job` also offers `stream(data)` for live output and `download(file_id, path)` for large files.

## Tests

```sh
docker compose -f workers/compose.test.yaml run --rm tests
```

The tests run against a real RabbitMQ and a mocked API (`respx`). `tests/test_readme.py` runs the example above.
