# Design agent: Claude Agent SDK (bundles the Claude Code CLI) as a slopoly_worker. Build context: repo root.
FROM python:3.13-slim

RUN pip install --no-cache-dir "claude-agent-sdk==0.2.182" "pytest>=9.2"
COPY workers/pyproject.toml /opt/slopoly/worker/pyproject.toml
COPY workers/slopoly_worker /opt/slopoly/worker/slopoly_worker
RUN pip install --no-cache-dir /opt/slopoly/worker && pip check     && ln -s "$(python -c 'import claude_agent_sdk, os; print(os.path.dirname(claude_agent_sdk.__file__))')/_bundled/claude" /usr/local/bin/claude

# Claude Code refuses some modes as root, and keeps sessions under ~/.claude (a named volume).
RUN useradd --create-home agent && mkdir -p /home/agent/.claude && chown agent /home/agent/.claude
COPY containers/agent/agent_worker.py /opt/slopoly/
ENV PYTHONUNBUFFERED=1 SLOPOLY_AGENT_DIR=/opt/slopoly/agent
USER agent
WORKDIR /opt/slopoly
CMD ["python", "agent_worker.py"]
