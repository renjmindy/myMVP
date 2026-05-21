# ChatGPT Task Scheduler — Exercise

## How to Use

1. Read `PROMPT.md`
2. Answer the Design Questions (write your answers directly in `PROMPT.md`)
3. Build the prototype:
   - **Challenge Track:** Build from scratch using `PROMPT.md` as your spec
   - **Guided Track:** Go to `scaffold/`, fill in the TODOs
4. Verify with the MCP inspector tests at the bottom of `PROMPT.md`
5. Bring your Design Questions answers to live session for discussion

## Choose Your Track

**Challenge Track** — You decide the architecture, file structure, and implementation. Any language with an MCP SDK works (Python + the official `mcp` SDK recommended). Read `PROMPT.md` to get started.

**Guided Track** — File structure and boilerplate are provided. Fill in the core logic marked with `TODO`. Go to `scaffold/` and follow the instructions below.

## Guided Track Setup

```bash
cd scaffold
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

You also need **Node.js** for `npx` (used by the MCP inspector for verification).

### Files to Fill In

| File | TODO | Design Decision |
|------|------|-----------------|
| `app/scheduler.py` | `get_time_bucket()` + `find_due_jobs()` | Time bucket partitioning for efficient job scanning |
| `app/mcp_server.py` | `TOOL_REGISTRY` + `route_tool_call()` | Registry pattern for MCP tool routing |

### Run and Verify

The prototype is a real MCP stdio server. Verify with the MCP inspector (no Claude needed):

```bash
npx @modelcontextprotocol/inspector python -m app.mcp_server
```

This opens a browser GUI — see `PROMPT.md` Verification section for the full test flow. Once the inspector tests pass, you can optionally connect to Claude Desktop / Claude Code (instructions also in `PROMPT.md`).

## Bonus Challenges

- Connect a real LLM to parse natural language task descriptions before calling `task.create`
- Add recurring job support (cron expressions)
- Add job chaining (Job A completes -> triggers Job B)
- Add MCP `resources` support (e.g., expose job details as readable resources)
- Add MCP `prompts` support (e.g., a `daily_review` prompt template)
