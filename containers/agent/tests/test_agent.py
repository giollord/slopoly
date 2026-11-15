"""agent-turn handler with a stubbed SDK query (no Claude, broker or API)."""
import asyncio
from types import SimpleNamespace

import claude_agent_sdk as sdk
import pytest

import agent_worker
from slopoly_worker import JobFailed


@pytest.fixture(autouse=True)
def env(monkeypatch):
    monkeypatch.setenv("CLAUDE_CODE_OAUTH_TOKEN", "token")
    monkeypatch.setenv("SLOPOLY_API_URL", "http://api:5000/")
    monkeypatch.setenv("SLOPOLY_WORKER_KEY", "key")


class FakeJob:
    def __init__(self, inputs):
        self.inputs, self.streamed = inputs, []
        self.message = SimpleNamespace(pack_id="pack-1")

    async def stream(self, data):
        self.streamed.append(data)


def result(**overrides):
    values = dict(subtype="success", duration_ms=1, duration_api_ms=1, is_error=False, num_turns=2,
                  session_id="session-2", total_cost_usd=0.01, result="done")
    values.update(overrides)
    return sdk.ResultMessage(**values)


def stub(monkeypatch, messages):
    seen = {}

    async def query(prompt, options):
        seen.update(prompt=prompt, options=options)
        for m in messages:
            yield m

    monkeypatch.setattr(agent_worker, "query", query)
    return seen


def run(inputs):
    job = FakeJob(inputs)
    return job, asyncio.run(agent_worker.turn(job))


def test_turn_resumes_session_streams_and_returns_new_session(monkeypatch):
    seen = stub(monkeypatch, [
        sdk.SystemMessage(subtype="init", data={"session_id": "session-2"}),
        sdk.AssistantMessage(content=[sdk.TextBlock(text="Writing the style."),
                                      sdk.ToolUseBlock(id="t1", name="mcp__slopoly__update_style", input={"styleText": "quirky"})],
                             model="claude"),
        sdk.UserMessage(content=[sdk.ToolResultBlock(tool_use_id="t1", content=[{"type": "text", "text": '{"id": "p"}'}],
                                                     is_error=False)]),
        sdk.AssistantMessage(content=[sdk.TextBlock(text="Style anchor started.")], model="claude"),
        result(),
    ])
    prompt = "[Context]\nThe user is on the pack page.\n[/Context]\n\nlow-poly gnome village"
    job, outputs = run({"message": "low-poly gnome village", "prompt": prompt, "sessionId": "session-1"})

    options = seen["options"]
    assert seen["prompt"] == prompt
    assert options.resume == "session-1" and options.tools == [] and options.allowed_tools == ["mcp__slopoly"]
    assert options.strict_mcp_config and options.max_turns == agent_worker.MAX_TURNS
    assert options.mcp_servers["slopoly"] == {"type": "http", "url": "http://api:5000/mcp", "headers": {"X-Worker-Key": "key"}}
    assert outputs == {"sessionId": "session-2", "reply": "Writing the style.\n\nStyle anchor started."}
    assert [e["kind"] for e in job.streamed] == ["session", "text", "tool_use", "tool_result", "text", "result"]
    assert job.streamed[0] == {"kind": "session", "sessionId": "session-2"}
    assert job.streamed[2]["name"] == "update_style" and job.streamed[3]["text"] == '{"id": "p"}'


@pytest.mark.parametrize("message", [
    result(is_error=True, subtype="error_during_execution", api_error_status=401, result="Invalid bearer token"),
    sdk.AssistantMessage(content=[], model="claude", error="authentication_failed"),
])
def test_rejected_credential_is_an_auth_error(monkeypatch, message):
    stub(monkeypatch, [message])
    with pytest.raises(JobFailed) as failure:
        run({"message": "hi"})
    assert failure.value.code == "auth" and "claude setup-token" in str(failure.value)


def test_missing_token_is_an_auth_error(monkeypatch):
    monkeypatch.delenv("CLAUDE_CODE_OAUTH_TOKEN")
    with pytest.raises(JobFailed) as failure:
        run({"message": "hi"})
    assert failure.value.code == "auth"


def test_message_without_prompt_is_sent_as_it_is(monkeypatch):
    seen = stub(monkeypatch, [result()])
    run({"message": "hi"})
    assert seen["prompt"] == "hi"


def test_cancel_closes_the_query(monkeypatch):
    """Stop cancels the handler task; the SDK generator must be closed so Claude Code ends at once."""
    state = {"closed": False}

    async def main():
        started = asyncio.Event()

        async def query(prompt, options):
            try:
                yield sdk.SystemMessage(subtype="init", data={"session_id": "session-9"})
                started.set()
                await asyncio.sleep(3600)
                yield result()
            finally:
                state["closed"] = True

        monkeypatch.setattr(agent_worker, "query", query)
        job = FakeJob({"message": "model the cart"})
        task = asyncio.create_task(agent_worker.turn(job))
        await started.wait()
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task
        return job

    job = asyncio.run(main())
    assert state["closed"]
    assert job.streamed == [{"kind": "session", "sessionId": "session-9"}]


def test_max_turns_ends_the_turn_without_failing(monkeypatch):
    stub(monkeypatch, [result(is_error=True, subtype="error_max_turns")])
    _, outputs = run({"message": "keep going"})
    assert outputs["sessionId"] == "session-2"
