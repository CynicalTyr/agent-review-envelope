"""Vendored path stub. Set AGENT_HOME to a throwaway directory."""
from __future__ import annotations

import os
from pathlib import Path

AGENT_HOME = Path(os.environ.get("AGENT_HOME", ".")).resolve()
OUTBOX = AGENT_HOME / "outbox"
OUTBOX_PENDING_SYSTEMS_REVIEW = OUTBOX / "pending_systems_review"
OUTBOX_PENDING_PRIMARY_REVIEW = OUTBOX / "pending_primary_review"
HEALTH_STATE = AGENT_HOME / "health" / "state"
WORKSPACE_DIR = AGENT_HOME
CAPACITY_GATE_YAML = AGENT_HOME / "config" / "capacity_gate.yaml"
LOOP_GUARDRAILS_JSONL = HEALTH_STATE / "loop_guardrails.jsonl"
SCARAB_INJECT_DEFAULTS: dict = {
    "loop_guardrails": {
        "enabled": True,
        "max_records": 500,
        "inject_max_chars": 300,
        "inject_max_rules": 5,
    }
}
OUTBOX_PENDING_CYNICAL0N3_REVIEW = OUTBOX_PENDING_PRIMARY_REVIEW
