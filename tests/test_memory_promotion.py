from __future__ import annotations

import shutil
import tempfile
import unittest
from pathlib import Path

from server.database import close_db
from server.memory_compile import compile_memory_views
from server.memory_promotion import promote_memory_event
from server.memory_runtime import append_memory_event, read_memory_views
from server.vault_contract import root_path
from server.vault_ops import ensure_vault_structure


class MemoryPromotionTest(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.mkdtemp()
        ensure_vault_structure(self.tmp)

    def tearDown(self) -> None:
        close_db(self.tmp)
        shutil.rmtree(self.tmp)

    def test_high_impact_memory_cannot_skip_provisional_stage(self) -> None:
        result = append_memory_event(
            self.tmp,
            event={
                "event_type": "preference_update",
                "view_keys": ["taste"],
                "trust_label": "user-stated",
                "status": "confirmed",
                "summary": "Failure analysis should dominate ranking.",
                "metadata": {
                    "preferred_venues": ["CoRL"],
                },
            },
        )

        self.assertFalse(result["ok"])
        self.assertIn("provisional first", result["error"])

    def test_promote_memory_event_writes_audit_artifact_and_confirmed_clone(self) -> None:
        append_result = append_memory_event(
            self.tmp,
            event={
                "event_type": "preference_update",
                "view_keys": ["taste"],
                "trust_label": "user-stated",
                "status": "provisional",
                "summary": "Failure analysis should dominate ranking.",
                "content": "Prefer grounded failure modes before leaderboard deltas.",
                "metadata": {
                    "preferred_venues": ["CoRL"],
                    "accepted_keywords": ["failure analysis"],
                },
            },
        )
        self.assertTrue(append_result["ok"])

        promoted = promote_memory_event(
            self.tmp,
            source_event_id=append_result["event_id"],
            decision_note="Confirmed after explicit review.",
        )
        self.assertTrue(promoted["ok"])
        self.assertTrue(promoted["promoted"])
        self.assertEqual(promoted["promoted_status"], "confirmed")
        self.assertEqual(promoted["promoted_event_state"], "appended")
        self.assertIsNotNone(promoted["promoted_event_id"])

        audit_path = Path(promoted["promotion_artifact_path"])
        self.assertTrue(audit_path.exists())
        self.assertIn("Confirmed after explicit review", audit_path.read_text(encoding="utf-8"))

        compile_result = compile_memory_views(self.tmp, view_keys=["taste"])
        self.assertTrue(compile_result["ok"])

        state = read_memory_views(self.tmp, view_keys=["taste"])
        self.assertFalse(state["overlay_applied"])
        body = state["views"]["taste"]["body"]
        self.assertEqual(body.count("Failure analysis should dominate ranking."), 1)
        self.assertIn("| user-stated | confirmed |", body)
        self.assertNotIn("| user-stated | provisional |", body)

    def test_low_impact_memory_can_still_write_confirmed_directly(self) -> None:
        result = append_memory_event(
            self.tmp,
            event={
                "event_type": "thread_update",
                "view_keys": ["active-threads"],
                "trust_label": "jointly-derived",
                "status": "confirmed",
                "summary": "Failure-aware planning is an active thread.",
                "metadata": {
                    "thread_id": "failure-aware-planning",
                    "thread_action": "enter",
                    "thread_title": "Failure-Aware Planning",
                },
            },
        )

        self.assertTrue(result["ok"])
        self.assertEqual(result["event"]["status"], "confirmed")

        promotions_dir = root_path(self.tmp, "memory_promotions")
        self.assertTrue(promotions_dir.exists())


if __name__ == "__main__":
    unittest.main()
