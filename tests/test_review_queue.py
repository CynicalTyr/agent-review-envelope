from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
os.environ.setdefault("AGENT_HOME", tempfile.mkdtemp())

from review_queue import build_review_payload, enqueue_systems_review, validate_review_payload


class ReviewEnvelopeTests(unittest.TestCase):
    def test_build_and_enqueue(self) -> None:
        payload = build_review_payload(
            source="demo",
            kind="sitrep",
            message="disk low",
            recipient="operator",
            recipient_role="admin",
            allow_code_blocks=True,
        )
        validate_review_payload(payload)
        path = enqueue_systems_review(payload)
        self.assertTrue(path.is_file())
        self.assertIn("cynical_review_envelope", path.read_text())

    def test_code_blocks_user_rejected(self) -> None:
        with self.assertRaises(ValueError):
            build_review_payload(
                source="demo",
                kind="sitrep",
                message="hi",
                recipient="user",
                recipient_role="user",
                allow_code_blocks=True,
            )


if __name__ == "__main__":
    unittest.main()
