"""Stage worker artifacts for two-tier review before any human channel.

Workers enqueue review envelopes to ``pending_systems_review`` first (systems/worker
tier: fix, reject noise, or ESCALATE). Escalated items land in
``pending_primary_review`` for the primary LLM or outbound dispatch.

Scheduled briefings may bypass both queues and write a dedicated outbox. That
exception is deliberate: latency and tone beat dual-control for news, not for
security sitreps.
"""

from __future__ import annotations

import json
import os
import time
from pathlib import Path
from typing import Any, Literal

from paths import OUTBOX_PENDING_PRIMARY_REVIEW, OUTBOX_PENDING_SYSTEMS_REVIEW

REVIEW_ENVELOPE_SCHEMA = "cynical_review_envelope"
REVIEW_ENVELOPE_VERSION = "1.0"
_VALID_RECIPIENT_ROLES = {"admin", "user"}
_VALID_CHANNELS = {"signal"}
_VALID_FORMATS = {"natural_language"}

ReviewQueue = Literal["systems", "primary"]


def _require_non_empty_text(value: Any, field_name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field_name} must be a non-empty string")
    return value.strip()


def build_review_payload(
    *,
    source: str,
    kind: str,
    message: str,
    recipient: str,
    recipient_role: str,
    details: dict[str, Any] | None = None,
    channel: str = "signal",
    summary: str | None = None,
    allow_code_blocks: bool = False,
) -> dict[str, Any]:
    """Build the required review-envelope payload for pending review items."""
    normalized_source = _require_non_empty_text(source, "source")
    normalized_kind = _require_non_empty_text(kind, "kind")
    normalized_message = _require_non_empty_text(message, "message")
    normalized_recipient = _require_non_empty_text(recipient, "recipient")
    normalized_role = _require_non_empty_text(recipient_role, "recipient_role").lower()
    normalized_channel = _require_non_empty_text(channel, "channel").lower()
    normalized_summary = (
        _require_non_empty_text(summary, "summary")
        if summary is not None
        else normalized_message.splitlines()[0][:160]
    )

    if normalized_role not in _VALID_RECIPIENT_ROLES:
        raise ValueError(
            f"recipient_role must be one of {sorted(_VALID_RECIPIENT_ROLES)}"
        )
    if normalized_channel not in _VALID_CHANNELS:
        raise ValueError(f"channel must be one of {sorted(_VALID_CHANNELS)}")
    if allow_code_blocks and normalized_role != "admin":
        raise ValueError("allow_code_blocks is only permitted for admin recipients")
    if details is not None and not isinstance(details, dict):
        raise ValueError("details must be a dict when provided")

    return {
        "schema": REVIEW_ENVELOPE_SCHEMA,
        "schema_version": REVIEW_ENVELOPE_VERSION,
        "source": normalized_source,
        "kind": normalized_kind,
        "summary": normalized_summary,
        "message": normalized_message,
        "delivery": {
            "channel": normalized_channel,
            "recipient": normalized_recipient,
            "recipient_role": normalized_role,
            "format": "natural_language",
            "allow_code_blocks": bool(allow_code_blocks),
        },
        "orchestrator": {
            "workflow": "review_validate_act_then_escalate",
            "autonomous_action_expected": True,
            "escalate_when": "unresolved_or_approval_required",
        },
        "details": details or {},
    }


def validate_review_payload(payload: dict[str, Any]) -> dict[str, Any]:
    """Validate a pending-review payload and return it unchanged when valid."""
    if not isinstance(payload, dict):
        raise ValueError("payload must be a dict")

    schema = payload.get("schema")
    if schema != REVIEW_ENVELOPE_SCHEMA:
        raise ValueError(f"schema must be {REVIEW_ENVELOPE_SCHEMA!r}")

    version = payload.get("schema_version")
    if version != REVIEW_ENVELOPE_VERSION:
        raise ValueError(f"schema_version must be {REVIEW_ENVELOPE_VERSION!r}")

    _require_non_empty_text(payload.get("source"), "source")
    _require_non_empty_text(payload.get("kind"), "kind")
    _require_non_empty_text(payload.get("summary"), "summary")
    _require_non_empty_text(payload.get("message"), "message")

    delivery = payload.get("delivery")
    if not isinstance(delivery, dict):
        raise ValueError("delivery must be a dict")
    channel = _require_non_empty_text(delivery.get("channel"), "delivery.channel").lower()
    recipient_role = _require_non_empty_text(
        delivery.get("recipient_role"), "delivery.recipient_role"
    ).lower()
    _require_non_empty_text(delivery.get("recipient"), "delivery.recipient")
    human_format = _require_non_empty_text(delivery.get("format"), "delivery.format").lower()
    allow_code_blocks = delivery.get("allow_code_blocks")

    if channel not in _VALID_CHANNELS:
        raise ValueError(f"delivery.channel must be one of {sorted(_VALID_CHANNELS)}")
    if recipient_role not in _VALID_RECIPIENT_ROLES:
        raise ValueError(
            f"delivery.recipient_role must be one of {sorted(_VALID_RECIPIENT_ROLES)}"
        )
    if human_format not in _VALID_FORMATS:
        raise ValueError(f"delivery.format must be one of {sorted(_VALID_FORMATS)}")
    if not isinstance(allow_code_blocks, bool):
        raise ValueError("delivery.allow_code_blocks must be a bool")
    if allow_code_blocks and recipient_role != "admin":
        raise ValueError("delivery.allow_code_blocks is only permitted for admin recipients")

    orchestrator = payload.get("orchestrator")
    if not isinstance(orchestrator, dict):
        raise ValueError("orchestrator must be a dict")
    if (
        orchestrator.get("workflow") != "review_validate_act_then_escalate"
        or orchestrator.get("autonomous_action_expected") is not True
        or orchestrator.get("escalate_when") != "unresolved_or_approval_required"
    ):
        raise ValueError("orchestrator contains an invalid workflow contract")

    details = payload.get("details")
    if not isinstance(details, dict):
        raise ValueError("details must be a dict")

    return payload


def _atomic_enqueue(
    payload: dict[str, Any],
    *,
    outbox_dir: Path,
    filename: str | None = None,
    default_prefix: str = "review",
) -> Path:
    """Write a validated review envelope atomically under ``outbox_dir``."""
    validate_review_payload(payload)
    outbox_dir.mkdir(parents=True, exist_ok=True)
    ts = int(time.time() * 1000)
    name = filename or f"{default_prefix}_{ts}.json"
    if not name.endswith(".json"):
        name = f"{name}.json"
    out_path = outbox_dir / name
    tmp_path = outbox_dir / f".{name}.tmp"
    with open(tmp_path, "w", encoding="utf-8") as handle:
        json.dump(payload, handle, indent=2)
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(tmp_path, out_path)
    return out_path


def enqueue_systems_review(payload: dict[str, Any], *, filename: str | None = None) -> Path:
    """Atomic JSON drop under ``pending_systems_review/`` (first review tier)."""
    return _atomic_enqueue(
        payload,
        outbox_dir=OUTBOX_PENDING_SYSTEMS_REVIEW,
        filename=filename,
        default_prefix="systems_review",
    )


def enqueue_pending_review(payload: dict[str, Any], *, filename: str | None = None) -> Path:
    """Atomic JSON drop under ``pending_primary_review/`` (primary LLM tier)."""
    return _atomic_enqueue(
        payload,
        outbox_dir=OUTBOX_PENDING_PRIMARY_REVIEW,
        filename=filename,
        default_prefix="review",
    )


def enqueue_review(
    payload: dict[str, Any],
    *,
    filename: str | None = None,
    queue: ReviewQueue = "systems",
) -> Path:
    """Enqueue to ``systems`` (default) or ``primary`` review outbox."""
    if queue == "primary":
        return enqueue_pending_review(payload, filename=filename)
    return enqueue_systems_review(payload, filename=filename)
