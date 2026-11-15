"""Detached jobs recorded in ``<pack>/jobs/<id>.yaml`` (see generation-jobs).

``start`` writes the job file and spawns ``python -m slopoly _job <file>`` detached from the caller, so the job outlives
the agent's shell. The job process records its pid and start time, runs the kind's handler and writes the result.
``wait`` only reads; a queued or running job whose process is gone is reported (and recorded) as ``orphaned``.
"""

from __future__ import annotations

import os
import secrets
import subprocess
import sys
import time
import traceback
from collections.abc import Callable
from datetime import datetime, timezone
from pathlib import Path

import psutil

from . import models as m
from .core import SlopolyError, load, write_yaml
from .workspace import Pack, Workspace

Handler = Callable[["JobContext"], dict]
KINDS: dict[str, Handler] = {}
DEFAULT_WAIT = 540  # seconds; under the ~10-minute limit of common agent shells
TERMINAL = ("succeeded", "failed", "cancelled")
SPAWN_GRACE = 60  # seconds a queued job may go without a pid before it counts as orphaned


def kind(name: str):
    def register(handler: Handler) -> Handler:
        KINDS[name] = handler
        return handler
    return register


def now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


class Cancelled(Exception):
    pass


class JobContext:
    """What a handler gets: the job, its pack, progress reporting and a cancellation check."""

    def __init__(self, pack: Pack, path: Path, job: m.Job):
        self.pack, self.path, self.job = pack, path, job
        self.ws: Workspace = pack.ws
        self.inputs = job.inputs

    def reload(self) -> m.Job:
        return load(m.Job, self.path)

    def update(self, **fields) -> None:
        current = self.reload()
        if current.cancel_requested:
            raise Cancelled()
        self.job = current.model_copy(update=fields)
        write_yaml(self.path, self.job)

    def progress(self, fraction: float, message: str | None = None) -> None:
        self.update(progress=round(max(0.0, min(1.0, fraction)), 3), message=message)

    def check(self) -> None:
        """Raises when the job was cancelled or its pack folder was deleted; call before writing outputs."""
        if not self.pack.file.exists():
            raise SlopolyError("pack_deleted", f"pack {self.pack.name!r} was deleted while the job ran")
        if self.reload().cancel_requested:
            raise Cancelled()

    def remember_prompt(self, prompt_id: str) -> None:
        """Records a ComfyUI prompt id so cancelling the job can drop it from ComfyUI's queue."""
        self.update(prompts=[*self.reload().prompts, prompt_id])


def jobs_of(pack: Pack) -> list[tuple[Path, m.Job]]:
    folder = pack.jobs_dir
    return [(p, refresh(p, load(m.Job, p))) for p in sorted(folder.glob("*.yaml"))] if folder.is_dir() else []


def open_jobs(pack: Pack) -> list[dict]:
    return [summary(j) for _, j in jobs_of(pack) if j.state not in TERMINAL]


def summary(job: m.Job) -> dict:
    out = {"id": job.id, "kind": job.kind, "target": job.target, "state": job.state, "progress": job.progress}
    if job.message:
        out["message"] = job.message
    return out


def locate(ws: Workspace, job_id: str) -> tuple[Pack, Path]:
    for pack in ws.packs():
        path = pack.jobs_dir / f"{job_id}.yaml"
        if path.exists():
            return pack, path
    raise SlopolyError("not_found", f"no job {job_id!r} in this workspace", "run slopoly jobs to list them")


def alive(job: m.Job) -> bool:
    if job.pid is None:
        return False
    try:
        process = psutil.Process(job.pid)
        return job.process_started is None or abs(process.create_time() - job.process_started) < 2
    except psutil.Error:
        return False


def refresh(path: Path, job: m.Job) -> m.Job:
    """Records an open job whose process is gone as failed (orphaned)."""
    if job.state in TERMINAL:
        return job
    if job.pid is None:
        created = datetime.fromisoformat(job.created).timestamp()
        if time.time() - created < SPAWN_GRACE:
            return job
    elif alive(job):
        return job
    job = job.model_copy(update={"state": "failed", "finished": now(), "error": m.JobError(
        code="orphaned", message="the job's process ended without a result (machine restart or crash)",
        hint=f"run slopoly retry {job.id}")})
    write_yaml(path, job)
    return job


def spawn(path: Path, cwd: Path) -> None:
    log = path.with_suffix(".log").open("ab")
    command = [sys.executable, "-m", "slopoly", "_job", str(path)]
    if sys.platform == "win32":
        flags = subprocess.CREATE_NEW_PROCESS_GROUP | subprocess.CREATE_NO_WINDOW
        try:  # leave the agent shell's job object, so killing the shell doesn't kill the job
            subprocess.Popen(command, cwd=cwd, stdin=subprocess.DEVNULL, stdout=log, stderr=log, close_fds=True,
                             creationflags=flags | subprocess.CREATE_BREAKAWAY_FROM_JOB)
        except OSError:
            subprocess.Popen(command, cwd=cwd, stdin=subprocess.DEVNULL, stdout=log, stderr=log, close_fds=True,
                             creationflags=flags)
    else:
        subprocess.Popen(command, cwd=cwd, stdin=subprocess.DEVNULL, stdout=log, stderr=log, close_fds=True,
                         start_new_session=True)
    log.close()


def start(pack: Pack, kind_name: str, target: str, inputs: dict, retry_of: str | None = None) -> dict:
    if kind_name not in KINDS:
        raise SlopolyError("unknown_kind", f"unknown job kind {kind_name!r}")
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    job = m.Job(id=f"{stamp}-{secrets.token_hex(2)}", kind=kind_name, target=target, inputs=inputs, created=now(),
                retry_of=retry_of)
    path = pack.jobs_dir / f"{job.id}.yaml"
    write_yaml(path, job)
    spawn(path, pack.ws.root.parent)
    return {"job": job.id, "kind": kind_name, "target": target, "state": "queued",
            "hint": f"slopoly wait {job.id}"}


def run(path: Path) -> int:
    """The job process."""
    from .workspace import Workspace as W

    pack_root = path.parent.parent
    pack = Pack(W(pack_root.parent), pack_root.name)
    job = load(m.Job, path)
    if job.state != "queued":
        return 1
    process = psutil.Process()
    write_yaml(path, job.model_copy(update={"pid": os.getpid(), "process_started": process.create_time(),
                                           "state": "running"}))
    context = JobContext(pack, path, load(m.Job, path))
    try:
        if job.cancel_requested:
            raise Cancelled()
        from . import generate, windows  # noqa: F401  (register their kinds)
        result = KINDS[job.kind](context)
        context.check()
        final = {"state": "succeeded", "result": result, "progress": 1.0}
    except Cancelled:
        final = {"state": "cancelled"}
    except SlopolyError as error:
        final = {"state": "failed", "error": m.JobError(code=error.code, message=error.message, hint=error.hint)}
    except Exception as error:  # an unexpected failure still finishes the job, with the trace in its log
        traceback.print_exc()
        final = {"state": "failed", "error": m.JobError(code="internal", message=f"{type(error).__name__}: {error}",
                                                        hint=f"see {path.with_suffix('.log').name}")}
    if not pack.file.exists():  # the pack was deleted: write nothing, not even the job file
        return 1
    current = load(m.Job, path)
    if current.cancel_requested and final["state"] == "succeeded":
        final = {"state": "cancelled", "result": None}
    write_yaml(path, current.model_copy(update={**final, "finished": now()}))
    sys.stdout.flush()
    return 0


def result_of(job: m.Job) -> dict:
    out = summary(job)
    if job.state in TERMINAL:
        out["finished"] = job.finished
    if job.result is not None:
        out["result"] = job.result
    if job.error:
        out["error"] = job.error.model_dump(exclude_none=True)
    return out


def wait(ws: Workspace, job_id: str, timeout: float = DEFAULT_WAIT) -> dict:
    _, path = locate(ws, job_id)
    deadline = time.monotonic() + max(0.0, timeout)
    while True:
        job = refresh(path, load(m.Job, path))
        if job.state in TERMINAL:
            return result_of(job)
        if time.monotonic() >= deadline:
            out = summary(job) | {"state": "pending", "job_state": job.state}
            return out | {"hint": f"the job is still {job.state}; run slopoly wait {job.id} again"}
        time.sleep(0.5)


def cancel(ws: Workspace, job_id: str) -> dict:
    pack, path = locate(ws, job_id)
    job = refresh(path, load(m.Job, path))
    if job.state in TERMINAL:
        raise SlopolyError("not_running", f"job {job_id} already {job.state}")
    write_yaml(path, job.model_copy(update={"cancel_requested": True}))
    deadline = time.monotonic() + 10
    while job.pid is None and time.monotonic() < deadline:  # a just-started job: let its process record itself
        time.sleep(0.1)
        job = load(m.Job, path)
        if job.state in TERMINAL:
            return result_of(job)
    if job.prompts:
        from .comfy.client import ComfyClient
        client = ComfyClient.from_config()
        for prompt_id in job.prompts:
            client.cancel(prompt_id)
    if job.pid and alive(job):
        try:
            process = psutil.Process(job.pid)
            for child in process.children(recursive=True):
                child.terminate()
            process.terminate()
            process.wait(10)
        except psutil.Error:
            pass
    job = load(m.Job, path)
    if job.state not in TERMINAL:
        job = job.model_copy(update={"state": "cancelled", "finished": now()})
        write_yaml(path, job)
    return result_of(job)


def retry(ws: Workspace, job_id: str) -> dict:
    pack, path = locate(ws, job_id)
    job = refresh(path, load(m.Job, path))
    if job.state not in ("failed", "cancelled"):
        raise SlopolyError("not_retryable", f"job {job_id} is {job.state}; only failed or cancelled jobs can be retried")
    return start(pack, job.kind, job.target, job.inputs, retry_of=job.id)


def cancel_all(pack: Pack) -> list[str]:
    cancelled = []
    for _, job in jobs_of(pack):
        if job.state not in TERMINAL:
            cancel(pack.ws, job.id)
            cancelled.append(job.id)
    return cancelled


@kind("sleep")
def sleep_job(context: JobContext) -> dict:
    """A job that only waits (for tests and for checking that detached jobs work on a machine)."""
    seconds = float(context.inputs.get("seconds", 1))
    steps = max(1, int(seconds / 0.2))
    for i in range(steps):
        time.sleep(seconds / steps)
        context.progress((i + 1) / steps)
    if context.inputs.get("fail"):
        raise SlopolyError("asked_to_fail", "the job was asked to fail")
    return {"slept": seconds}
