# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What This Is

A learning exercise: build a job scheduler exposed as an MCP (Model Context Protocol) stdio server. Two tracks:
- **`scaffold/`** — boilerplate with `TODO` markers to fill in
- **`answers/`** — complete reference implementation

## Setup

Work inside either `scaffold/` or `answers/`:

```bash
cd answers          # or scaffold/
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

Requires Node.js for the MCP inspector (`npx`).

## Run and Verify

```bash
# Sanity check — process should hang on stdin (correct for stdio MCP server)
python -m app.mcp_server

# Full GUI verification — opens browser at http://localhost:5173
npx @modelcontextprotocol/inspector python -m app.mcp_server
```

No unit tests; verification is done through the MCP inspector GUI (see `PROMPT.md` for the step-by-step test flow).

## Architecture

```
MCP Tool Call → route_tool_call() → handler → SQLite (SQLAlchemy)
                                                      ↓
                              watcher_loop (thread) scans by time_bucket
                                                      ↓
                                              in-memory Queue
                                                      ↓
                                          worker_loop (thread) executes
```

**Key design decisions baked into the code:**

1. **Time bucket partitioning** — `jobs.time_bucket` stores `YYYYMMDDHH` (e.g. `"2026051910"`). The watcher only queries the current hour's bucket instead of scanning all rows. The composite index `idx_bucket_status` covers `(time_bucket, status)`.

2. **Registry pattern** — `TOOL_REGISTRY` in `mcp_server.py` maps tool names to handler functions. `route_tool_call()` does a single dict lookup. Adding a new tool means adding one entry to `TOOL_REGISTRY` and one `Tool` definition to `TOOL_DEFINITIONS`.

3. **Watcher + Queue + Worker separation** — `watcher_loop` only scans and enqueues (marks jobs `queued`); `worker_loop` only executes. The in-memory `queue.Queue` decouples them, simulating SQS.

4. **Tool naming** — `task.create`, `task.status`, etc. (namespace + action verb) for better LLM tool selection accuracy.

## MCP stdio constraint

**MCP uses stdout for protocol messages.** Any `print()` statement or logging to stdout will corrupt the protocol. Always write to stderr:

```python
logging.basicConfig(stream=sys.stderr)
```

## Files

```
app/
├── mcp_server.py   # Tool handlers, TOOL_DEFINITIONS, TOOL_REGISTRY, MCP entry point
├── scheduler.py    # get_time_bucket(), watcher_loop, worker_loop, start_scheduler()
├── models.py       # Job SQLAlchemy model with time_bucket + composite index
└── database.py     # SQLite engine, SessionLocal, Base
```

The scaffold versions of `scheduler.py` and `mcp_server.py` have `TODO` blocks where the core logic is missing.

## Connect to Claude Desktop / Claude Code

After inspector tests pass, add to the MCP config (use absolute paths):

```json
{
  "mcpServers": {
    "task-scheduler": {
      "command": "/absolute/path/to/answers/.venv/bin/python",
      "args": ["-m", "app.mcp_server"],
      "cwd": "/absolute/path/to/answers"
    }
  }
}
```

For Claude Code: edit `~/.claude/settings.json` or run `claude mcp add task-scheduler <python-path> -m app.mcp_server` from inside `answers/`.
