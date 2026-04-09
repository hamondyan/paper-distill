from __future__ import annotations

import shutil
import tempfile
import unittest
from pathlib import Path

import yaml

from server.database import close_db
from server.dialogue_capture import capture_dialogue
from server.memory_runtime import read_memory_views
from server.vault_contract import root_path
from server.vault_ops import ensure_vault_structure


def _read_frontmatter(path: Path) -> dict:
    content = path.read_text(encoding="utf-8")
    _, remainder = content.split("---\n", 1)
    fm_text, _ = remainder.split("\n---\n", 1)
    return yaml.safe_load(fm_text) or {}


class DialogueCaptureRuntimeTest(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.mkdtemp()
        ensure_vault_structure(self.tmp)

    def tearDown(self) -> None:
        close_db(self.tmp)
        shutil.rmtree(self.tmp)

    def _proposal(self) -> dict:
        return {
            "title": "Preference for failure-aware triage",
            "summary": "User wants failure analysis and negative results to dominate quick paper triage.",
            "content": "Prefer explicit failure modes over small leaderboard gains.",
            "proposal_note": "This should survive beyond the current chat because it affects ranking and filtering.",
            "evidence_excerpt": "Prioritize papers that explain why systems fail, not just that they improved.",
            "view_keys": ["assistant-brief", "taste"],
            "trust_label": "user-stated",
            "accepted_status": "provisional",
            "source": {
                "kind": "dialogue",
                "turn_id": "turn-42",
                "conversation_id": "conv-7",
            },
            "metadata": {
                "flow": "dialogue_capture_test",
            },
        }

    def test_propose_writes_dialogue_artifact_without_memory_append(self) -> None:
        result = capture_dialogue(
            self.tmp,
            action="propose",
            proposal=self._proposal(),
        )

        self.assertTrue(result["ok"])
        self.assertEqual(result["capture_state"], "proposed")
        self.assertEqual(result["decision"], "pending")
        self.assertEqual(result["memory_write_state"], "pending_user_decision")

        note_path = Path(result["dialogue_path"])
        self.assertTrue(note_path.exists())
        frontmatter = _read_frontmatter(note_path)
        self.assertEqual(frontmatter["type"], "dialogue-capture")
        self.assertEqual(frontmatter["capture_state"], "proposed")
        self.assertEqual(frontmatter["view_keys"], ["assistant-brief", "taste"])
        self.assertEqual(frontmatter["source"]["turn_id"], "turn-42")
        self.assertIn("This should survive beyond the current chat", note_path.read_text(encoding="utf-8"))

        memory_state = read_memory_views(self.tmp, view_keys=["assistant-brief", "taste"])
        self.assertFalse(memory_state["overlay_applied"])
        self.assertEqual(memory_state["views"]["assistant-brief"]["overlay_count"], 0)
        self.assertEqual(memory_state["views"]["taste"]["overlay_count"], 0)

    def test_propose_rejects_high_impact_confirmed_memory_without_promotion(self) -> None:
        proposal = self._proposal()
        proposal["accepted_status"] = "confirmed"

        result = capture_dialogue(
            self.tmp,
            action="propose",
            proposal=proposal,
        )

        self.assertFalse(result["ok"])
        self.assertIn("provisional first", result["error"])

    def test_accept_appends_memory_event_and_links_dialogue_artifact(self) -> None:
        proposed = capture_dialogue(
            self.tmp,
            action="propose",
            proposal=self._proposal(),
        )

        accepted = capture_dialogue(
            self.tmp,
            action="accept",
            capture_id=proposed["capture_id"],
            decision_note="Accepted as stable preference memory.",
        )

        self.assertTrue(accepted["ok"])
        self.assertEqual(accepted["capture_state"], "accepted")
        self.assertEqual(accepted["decision"], "accept")
        self.assertEqual(accepted["memory_write_state"], "appended")
        self.assertIsNotNone(accepted["memory_mutation_id"])
        self.assertIsNotNone(accepted["memory_event_id"])

        note_path = Path(accepted["dialogue_path"])
        frontmatter = _read_frontmatter(note_path)
        self.assertEqual(frontmatter["capture_state"], "accepted")
        self.assertEqual(frontmatter["decision_note"], "Accepted as stable preference memory.")
        self.assertEqual(frontmatter["memory_write_state"], "queued")
        self.assertEqual(frontmatter["memory_mutation_id"], accepted["memory_mutation_id"])

        first_read = read_memory_views(self.tmp, view_keys=["assistant-brief", "taste"])
        self.assertTrue(first_read["overlay_applied"])
        brief_overlay = first_read["views"]["assistant-brief"]["overlay_events"][0]
        self.assertEqual(brief_overlay["event_id"], accepted["memory_event_id"])
        self.assertEqual(brief_overlay["status"], "provisional")
        self.assertEqual(
            brief_overlay["metadata"]["dialogue_capture_id"],
            proposed["capture_id"],
        )

        second_read = read_memory_views(self.tmp, view_keys=["assistant-brief", "taste"])
        self.assertFalse(second_read["overlay_applied"])
        self.assertTrue((root_path(self.tmp, "memory") / "assistant-brief.md").exists())
        self.assertIn(
            "failure analysis and negative results",
            second_read["views"]["assistant-brief"]["body"],
        )

    def test_reject_keeps_dialogue_artifact_and_does_not_pollute_memory(self) -> None:
        proposed = capture_dialogue(
            self.tmp,
            action="propose",
            proposal=self._proposal(),
        )

        rejected = capture_dialogue(
            self.tmp,
            action="reject",
            capture_id=proposed["capture_id"],
            decision_note="Too speculative to keep as durable memory.",
        )

        self.assertTrue(rejected["ok"])
        self.assertEqual(rejected["capture_state"], "rejected")
        self.assertEqual(rejected["memory_write_state"], "skipped")
        self.assertIsNone(rejected["memory_mutation_id"])

        note_path = Path(rejected["dialogue_path"])
        frontmatter = _read_frontmatter(note_path)
        self.assertEqual(frontmatter["capture_state"], "rejected")
        self.assertEqual(frontmatter["decision"], "reject")
        self.assertEqual(frontmatter["memory_write_state"], "skipped")

        memory_state = read_memory_views(self.tmp, view_keys=["assistant-brief", "taste"])
        self.assertFalse(memory_state["overlay_applied"])
        self.assertEqual(memory_state["views"]["assistant-brief"]["overlay_count"], 0)
        self.assertEqual(memory_state["views"]["taste"]["overlay_count"], 0)

    def test_accept_after_reject_is_blocked(self) -> None:
        proposed = capture_dialogue(
            self.tmp,
            action="propose",
            proposal=self._proposal(),
        )
        rejected = capture_dialogue(
            self.tmp,
            action="reject",
            capture_id=proposed["capture_id"],
        )
        self.assertTrue(rejected["ok"])

        accepted = capture_dialogue(
            self.tmp,
            action="accept",
            capture_id=proposed["capture_id"],
        )
        self.assertFalse(accepted["ok"])
        self.assertIn("already rejected", accepted["error"])

    def test_accept_active_thread_dialogue_compiles_into_active_threads_view(self) -> None:
        proposed = capture_dialogue(
            self.tmp,
            action="propose",
            proposal={
                "title": "Failure-aware planning thread",
                "summary": "We are actively tracking failure-aware embodied planning as an open loop.",
                "content": "Keep following recovery-heavy planning papers and related idea drafts.",
                "view_keys": ["active-threads"],
                "trust_label": "jointly-derived",
                "accepted_status": "confirmed",
                "source": {
                    "kind": "dialogue",
                    "turn_id": "turn-99",
                    "conversation_id": "conv-9",
                },
                "metadata": {
                    "thread_id": "failure-aware-planning",
                    "thread_action": "enter",
                    "thread_title": "Failure-Aware Planning",
                },
            },
        )

        accepted = capture_dialogue(
            self.tmp,
            action="accept",
            capture_id=proposed["capture_id"],
        )
        self.assertTrue(accepted["ok"])
        self.assertEqual(accepted["memory_write_state"], "appended")

        first_read = read_memory_views(self.tmp, view_keys=["active-threads"])
        self.assertTrue(first_read["overlay_applied"])
        self.assertEqual(first_read["views"]["active-threads"]["overlay_count"], 1)
        self.assertEqual(
            first_read["views"]["active-threads"]["overlay_events"][0]["metadata"]["thread_id"],
            "failure-aware-planning",
        )

        second_read = read_memory_views(self.tmp, view_keys=["active-threads"])
        self.assertFalse(second_read["overlay_applied"])
        self.assertIn(
            "Failure-Aware Planning",
            second_read["views"]["active-threads"]["body"],
        )


if __name__ == "__main__":
    unittest.main()
