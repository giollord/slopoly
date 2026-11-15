"""Design agent worker: one chat message = one agent-turn job (design section 9).

agent-turn: inputs {message, prompt, sessionId, chatId}. The API composes the prompt (the message with the chat's page
context, or a line naming the page the user is on); it is sent as it is. Runs Claude Code through the Agent SDK with
only the Slopoly MCP tools, resumes the chat's session, streams messages as job events ({kind: session|text|tool_use|
tool_result|result, ...}) and returns {sessionId, reply}. The session event comes first, so a stopped (cancelled) turn
still leaves its session for the next message. A rejected credential fails the job with code "auth" so the UI can show
how to re-authorise.
"""

from __future__ import annotations

import contextlib
import os
from typing import Any

import claude_agent_sdk as sdk

from slopoly_worker import Job, JobFailed, run

AGENT_DIR = os.environ.get("SLOPOLY_AGENT_DIR", "/opt/slopoly/agent")
MAX_TURNS = int(os.environ.get("SLOPOLY_AGENT_MAX_TURNS", "40"))
RESULT_PREVIEW = 2000  # characters of a tool result shown in the chat
AUTH_STEPS = ("Run `claude setup-token`, store the token in the claude-oauth-token parameter (user secrets of "
              "Slopoly.AppHost) and restart the app. See README, \"Authorising the agent\".")

query = sdk.query  # replaced by a stub in tests


def options(session_id: str | None) -> sdk.ClaudeAgentOptions:
    return sdk.ClaudeAgentOptions(
        tools=[],  # no shell, file or web tools: the app is reached only through MCP
        mcp_servers={"slopoly": {"type": "http", "url": os.environ["SLOPOLY_API_URL"].rstrip("/") + "/mcp",
                                 "headers": {"X-Worker-Key": os.environ["SLOPOLY_WORKER_KEY"]}}},
        strict_mcp_config=True,
        allowed_tools=["mcp__slopoly"],
        resume=session_id or None,
        max_turns=MAX_TURNS,
        cwd=AGENT_DIR,
        setting_sources=["project"],  # agent/CLAUDE.md
        model=os.environ.get("SLOPOLY_AGENT_MODEL") or None,
    )


def text_of(content: Any) -> str:
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        return "\n".join(c.get("text", f"[{c.get('type')}]") if isinstance(c, dict) else str(c) for c in content)
    return "" if content is None else str(content)


def is_auth_error(message: Any) -> bool:
    if isinstance(message, sdk.ResultMessage):
        return message.api_error_status in (401, 403)
    if isinstance(message, sdk.AssistantMessage):
        return message.error == "authentication_failed"
    return False


async def turn(job: Job) -> dict[str, Any]:
    if not os.environ.get("CLAUDE_CODE_OAUTH_TOKEN"):
        raise JobFailed("The agent has no Claude credential. " + AUTH_STEPS, "auth")
    prompt = (job.inputs.get("prompt") or job.inputs.get("message") or "").strip()
    if not prompt:
        raise JobFailed("The message is empty.", "bad_request")

    session_id, reply = job.inputs.get("sessionId"), []
    # aclosing: a cancel (the user's Stop) closes the SDK generator, which ends the Claude Code process at once.
    async with contextlib.aclosing(query(prompt=prompt, options=options(session_id))) as items:
        async for item in items:
            if is_auth_error(item):
                raise JobFailed("Claude rejected the agent's credential (expired or revoked). " + AUTH_STEPS, "auth")
            if isinstance(item, sdk.SystemMessage) and item.subtype == "init":
                session_id = item.data.get("session_id", session_id)
                await job.stream({"kind": "session", "sessionId": session_id})
            elif isinstance(item, sdk.AssistantMessage):
                for block in item.content:
                    if isinstance(block, sdk.TextBlock) and block.text.strip():
                        reply.append(block.text)
                        await job.stream({"kind": "text", "text": block.text})
                    elif isinstance(block, sdk.ToolUseBlock):
                        await job.stream({"kind": "tool_use", "id": block.id, "name": block.name.removeprefix("mcp__slopoly__"),
                                          "input": block.input})
            elif isinstance(item, sdk.UserMessage) and isinstance(item.content, list):
                for block in item.content:
                    if isinstance(block, sdk.ToolResultBlock):
                        await job.stream({"kind": "tool_result", "id": block.tool_use_id, "isError": bool(block.is_error),
                                          "text": text_of(block.content)[:RESULT_PREVIEW]})
            elif isinstance(item, sdk.ResultMessage):
                session_id = item.session_id or session_id
                await job.stream({"kind": "result", "turns": item.num_turns, "costUsd": item.total_cost_usd,
                                  "stopReason": item.subtype})
                if item.is_error and item.subtype != "error_max_turns":
                    raise JobFailed(f"The agent stopped with an error: {item.result or item.subtype}", "agent_error")
    return {"sessionId": session_id, "reply": "\n\n".join(reply)}


if __name__ == "__main__":
    run({"agent-turn": turn})
