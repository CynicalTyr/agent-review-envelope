#!/usr/bin/env python3
"""Read-only MCP tools so an IDE agent can *see* pending review JSON.

The chat model must not write the outbox. Your worker daemon enqueues.
"""
from __future__ import annotations

import os
from pathlib import Path

try:
    from mcp.server.fastmcp import FastMCP
except ImportError as exc:  # pragma: no cover
    raise SystemExit("pip install 'agent-review-envelope[mcp]'") from exc

from paths import OUTBOX_PENDING_SYSTEMS_REVIEW, OUTBOX_PENDING_PRIMARY_REVIEW

mcp = FastMCP("agent-review-envelope")


def _list_json(folder: Path) -> list[str]:
    if not folder.is_dir():
        return []
    return sorted(p.name for p in folder.glob("*.json") if not p.name.startswith("."))


@mcp.tool()
def review_envelope_health() -> dict:
    """Is AGENT_HOME writable and are the outbox folders present?"""
    home = os.environ.get("AGENT_HOME", ".")
    return {
        "agent_home": str(Path(home).resolve()),
        "systems_pending": _list_json(OUTBOX_PENDING_SYSTEMS_REVIEW),
        "primary_pending": _list_json(OUTBOX_PENDING_PRIMARY_REVIEW),
    }


@mcp.tool()
def review_envelope_read(queue: str, filename: str) -> str:
    """Read one pending envelope. queue is 'systems' or 'primary'."""
    base = (
        OUTBOX_PENDING_SYSTEMS_REVIEW
        if queue.strip().lower() == "systems"
        else OUTBOX_PENDING_PRIMARY_REVIEW
    )
    path = (base / filename).resolve()
    if base.resolve() not in path.parents and path.parent != base.resolve():
        return "STATUS: BLOCKED\nWHY: path escape"
    if not path.is_file():
        return "STATUS: missing"
    return path.read_text(encoding="utf-8")[:8000]


if __name__ == "__main__":
    mcp.run()
