#!/usr/bin/env python3
"""60-second demo: drop a review envelope without messaging a human."""
from __future__ import annotations

import os
import tempfile

os.environ.setdefault("AGENT_HOME", tempfile.mkdtemp())

from review_queue import build_review_payload, enqueue_systems_review

payload = build_review_payload(
    source="nightly_disk_check",
    kind="sitrep",
    message="Free disk is under 2 GiB. Heavy tools should stay off.",
    recipient="operator",
    recipient_role="admin",
    summary="Low disk",
    allow_code_blocks=True,
)
path = enqueue_systems_review(payload)
print("enqueued:", path)
print(path.read_text()[:500])
