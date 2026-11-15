"""Detached jobs, with the 'sleep' kind (real detached processes)."""

import time

import psutil
import yaml

from slopoly import jobs, workspace


def job_file(pack, job_id):
    return pack / "jobs" / f"{job_id}.yaml"


def test_start_wait_finish(run, pack):
    started = run("_sleep", "gnome-village", "--seconds", "2").json
    assert started["state"] == "queued" and started["job"]
    pending = run("wait", started["job"], "--timeout", "0.3").json
    assert pending["state"] == "pending"
    done = run("wait", started["job"], "--timeout", "30").json
    assert done["state"] == "succeeded" and done["result"] == {"slept": 2.0}
    again = run("wait", started["job"], "--timeout", "0").json
    assert again == done
    assert run("jobs", "--all").json["jobs"][0]["state"] == "succeeded"


def test_failure_is_recorded(run, pack):
    job = run("_sleep", "gnome-village", "--seconds", "0.2", "--fail").json["job"]
    done = run("wait", job, "--timeout", "30").json
    assert done["state"] == "failed" and done["error"]["code"] == "asked_to_fail"


def test_cancel_and_retry(run, pack):
    job = run("_sleep", "gnome-village", "--seconds", "30").json["job"]
    deadline = time.time() + 20
    while yaml.safe_load(job_file(pack, job).read_text()).get("pid") is None and time.time() < deadline:
        time.sleep(0.2)
    pid = yaml.safe_load(job_file(pack, job).read_text())["pid"]
    assert run("cancel", job).json["state"] == "cancelled"
    assert not psutil.pid_exists(pid) or psutil.Process(pid).status() == psutil.STATUS_ZOMBIE
    assert run("cancel", job, ok=False).json["code"] == "not_running"
    retried = run("retry", job).json
    assert retried["job"] != job
    new = yaml.safe_load(job_file(pack, retried["job"]).read_text())
    assert new["retry_of"] == job and new["inputs"]["seconds"] == 30
    run("cancel", retried["job"])


def test_orphan_after_kill(run, pack):
    job = run("_sleep", "gnome-village", "--seconds", "30").json["job"]
    deadline = time.time() + 20
    while yaml.safe_load(job_file(pack, job).read_text()).get("pid") is None and time.time() < deadline:
        time.sleep(0.2)
    psutil.Process(yaml.safe_load(job_file(pack, job).read_text())["pid"]).kill()
    time.sleep(0.5)
    listed = run("jobs", "--all").json["jobs"][0]
    assert listed["state"] == "failed" and listed["error"]["code"] == "orphaned"
    assert run("wait", job).json["error"]["code"] == "orphaned"


def test_pack_deleted_while_running(run, pack):
    job = run("_sleep", "gnome-village", "--seconds", "30").json["job"]
    assert run("pack", "rm", "gnome-village", ok=False).json["code"] == "confirm_required"
    assert run("pack", "rm", "gnome-vilage", "--yes", ok=False).json["code"] == "not_found"
    result = run("pack", "rm", "gnome-village", "--yes").json
    assert result["cancelled_jobs"] == [job] and not pack.exists()
    time.sleep(1)
    assert not pack.exists()


def test_status_lists_open_jobs(run, pack):
    job = run("_sleep", "gnome-village", "--seconds", "5").json["job"]
    status = run("status", "gnome-village").json
    assert status["packs"][0]["open_jobs"][0]["id"] == job
    run("cancel", job)
