# MCP adapter

The library is **not** an MCP server. Workers write JSON via `review_queue.py`.
Chat/IDE agents **read** the outbox through **MCP** so the model sees tools,
not a send-chat primitive.

```
MCP host (Claude Desktop, Cursor, custom runtime)
    │  stdio JSON-RPC
    ▼
examples/mcp_server.py     ← this repo, runs next to the agent
    │  reads files
    ▼
$AGENT_HOME/outbox/pending_systems_review/*.json
$AGENT_HOME/outbox/pending_primary_review/*.json
```

Keeping MCP read-only means:

- The chat model cannot page a human by “helping.”
- Tool schemas stay stable if you change poller internals.
- Stdout of the MCP process stays a clean JSON-RPC pipe (logs on stderr).

## Tools

| Tool | Maps to | Returns |
| ---- | ------- | ------- |
| `review_envelope_health` | list `*.json` | `{agent_home, systems_pending, primary_pending}` |
| `review_envelope_read` | read one file | envelope JSON (truncated) or `STATUS: missing` |

`review_envelope_read` arguments: `queue` (`systems` or `primary`),
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

Worker enqueue recipes: [`INTEGRATION.md`](INTEGRATION.md).
