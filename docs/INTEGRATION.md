# Integration patterns

MCP tools in `examples/mcp_server.py` are a **read-only** client of the
filesystem outbox. Workers write with `review_queue.py`. Do not invert that.

```
MCP host (Cursor, Claude Desktop, custom runtime)
    │  stdio JSON-RPC
    ▼
examples/mcp_server.py     ← this repo, runs next to the agent
    │  reads files
    ▼
$AGENT_HOME/outbox/pending_systems_review/*.json
$AGENT_HOME/outbox/pending_primary_review/*.json

Meanwhile, your worker process:
    enqueue_systems_review(...)  →  same directories
```

Keeping MCP read-only means:

- The chat model cannot page a human by “helping.”
- Tool schemas stay stable if you change poller internals.
- Stdout of the MCP process stays a clean JSON-RPC pipe (log to stderr).

## Tools

| Tool | Maps to | Returns |
| ---- | ------- | ------- |
| `review_envelope_health` | list `*.json` in both queues | `{agent_home, systems_pending, primary_pending}` |
| `review_envelope_read` | read one file | envelope JSON (truncated) or `STATUS: missing` |

Arguments for `review_envelope_read`: `queue` (`systems` or `primary`),
`filename` (basename only). Path escape is blocked.

## Install (agent host)

```bash
python3 -m pip install -r examples/requirements-mcp.txt
```

## Configure a host

Copy `examples/mcp.example.json`. Use an **absolute** path to
`examples/mcp_server.py`. Set `AGENT_HOME` to a demo directory first.

Restart the MCP host after editing. Only the MCP SDK may write to stdout.

## How agents should use the tools

1. **Health** at the start of a session.
2. **Read** one envelope. Summarize `summary` / `kind` for the operator.
3. Do **not** claim a messenger already fired.
4. Do **not** invent a verdict. Verdicts belong to your reviewer poller.

## Locally built agent (no MCP)

```python
from review_queue import build_review_payload, enqueue_systems_review, enqueue_pending_review

env = build_review_payload(
    source="watchdog",
    kind="capacity_pressure",
    message="...",
    recipient="operator",
    recipient_role="admin",
    allow_code_blocks=True,
)
enqueue_systems_review(env)
# Later, only the reviewer process:
# enqueue_pending_review(escalated)
```

Poll with `pathlib.Path.glob("*.json")`, ignore names starting with `.`.
Consume by `rename` to a `done/` or `rejected/` folder after judging.

## Paste-ready worker policy

> File a review envelope for anything that would page a human. Never send
> chat from this process. If enqueue raises, log to stderr and skip — do
> not fall back to a DM.
