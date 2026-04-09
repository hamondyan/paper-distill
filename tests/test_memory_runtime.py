from __future__ import annotations

import json
import shutil
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from server.database import close_db
from server.memory_runtime import (
    append_memory_event,
    list_uncompiled_memory_events,
    read_memory_views,
)
from server.runtime import get_mutation_record
from server.vault_contract import root_path
from server.vault_ops import ensure_vault_structure, write_markdown


class MemoryRuntimeTest(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.mkdtemp()
        ensure_vault_structure(self.tmp)

    def tearDown(self) -> None:
        close_db(self.tmp)
        shutil.rmtree(self.tmp)

    def test_append_memory_event_is_event_first_and_does_not_rewrite_current_view(self) -> None:
        result = append_memory_event(
            self.tmp,
            event={
                "event_type": "dialogue_capture",
                "view_keys": ["taste"],
                "trust_label": "user-stated",
                "summary": "User said negative results matter more than headline benchmark gains.",
                "source": {"kind": "dialogue", "turn_id": "turn-1"},
            },
        )

        self.assertTrue(result["ok"])
        self.assertTrue(result["appended"])
        self.assertTrue(result["remembered"])
        self.assertFalse(result["compiled"])
        self.assertTrue(result["overlay_available"])

        event_path = Path(result["event_path"])
        self.assertTrue(event_path.exists())
        persisted = json.loads(event_path.read_text(encoding="utf-8"))
        self.assertEqual(persisted["event_id"], result["event_id"])
        self.assertEqual(persisted["compile_status"], "pending")
        self.assertEqual(persisted["view_keys"], ["taste"])

        memory_view = root_path(self.tmp, "memory") / "taste.md"
        self.assertFalse(memory_view.exists())

        mutation = get_mutation_record(self.tmp, result["mutation_id"])
        self.assertEqual(mutation["status"], "done")
        self.assertTrue(mutation["result"]["appended"])

    def test_read_memory_views_overlays_recent_uncompiled_events(self) -> None:
        write_markdown(
            root_path(self.tmp, "memory") / "taste.md",
            {"view_key": "taste", "compiled_at": "2026-04-09T10:00:00"},
            "# Taste\n\nCompiled memory says to prefer robotics papers with grounded evaluations.",
        )

        append_memory_event(
            self.tmp,
            event={
                "event_type": "dialogue_capture",
                "view_key": "taste",
                "trust_label": "user-stated",
                "summary": "User just clarified that negative results are especially valuable.",
                "source": {"kind": "dialogue", "turn_id": "turn-2"},
            },
        )

        memory_state = read_memory_views(self.tmp, view_keys=["taste"])
        self.assertTrue(memory_state["overlay_applied"])
        self.assertEqual(memory_state["uncompiled_event_count"], 1)

        taste_view = memory_state["views"]["taste"]
        self.assertTrue(taste_view["compiled"])
        self.assertIn("prefer robotics papers", taste_view["body"])
        self.assertEqual(taste_view["overlay_count"], 1)
        self.assertEqual(
            taste_view["overlay_events"][0]["summary"],
            "User just clarified that negative results are especially valuable.",
        )

        pending = list_uncompiled_memory_events(self.tmp, view_keys=["taste"])
        self.assertEqual(len(pending), 1)
        self.assertEqual(pending[0]["compile_status"], "pending")

    def test_append_memory_event_is_visible_to_next_read_before_compile_runs(self) -> None:
        write_markdown(
            root_path(self.tmp, "memory") / "taste.md",
            {"view_key": "taste", "compiled_at": "2026-04-09T09:30:00"},
            "# Taste\n\nCompiled memory says grounded robotics evidence matters.",
        )

        append_result = append_memory_event(
            self.tmp,
            event={
                "event_type": "dialogue_capture",
                "view_keys": ["taste", "assistant-brief"],
                "trust_label": "user-stated",
                "summary": "User wants failure analysis and negative results to outrank benchmark-only gains.",
                "content": "Prioritize explicit failure modes before small leaderboard improvements.",
                "source": {"kind": "dialogue", "turn_id": "turn-3"},
            },
        )

        self.assertTrue(append_result["ok"])
        self.assertTrue(append_result["overlay_available"])

        next_read = read_memory_views(self.tmp, view_keys=["taste", "assistant-brief"])
        self.assertTrue(next_read["overlay_applied"])
        self.assertEqual(next_read["uncompiled_event_count"], 1)

        taste_view = next_read["views"]["taste"]
        self.assertTrue(taste_view["compiled"])
        self.assertIn("grounded robotics evidence", taste_view["body"])
        self.assertEqual(taste_view["overlay_count"], 1)
        self.assertEqual(
            taste_view["overlay_events"][0]["event_id"],
            append_result["event_id"],
        )

        brief_view = next_read["views"]["assistant-brief"]
        self.assertFalse(brief_view["compiled"])
        self.assertEqual(brief_view["body"], "")
        self.assertEqual(brief_view["overlay_count"], 1)
        self.assertEqual(
            brief_view["overlay_events"][0]["summary"],
            "User wants failure analysis and negative results to outrank benchmark-only gains.",
        )

        self.assertFalse((root_path(self.tmp, "memory") / "assistant-brief.md").exists())

    def test_append_memory_event_failure_does_not_claim_success(self) -> None:
        with patch("server.memory_runtime._atomic_write_json", side_effect=OSError("disk full")):
            result = append_memory_event(
                self.tmp,
                event={
                    "event_type": "dialogue_capture",
                    "view_keys": ["profile"],
                    "trust_label": "jointly-derived",
                    "summary": "User is focused on embodied AI for household robotics.",
                },
            )

        self.assertFalse(result["ok"])
        self.assertFalse(result["appended"])
        self.assertFalse(result["remembered"])
        self.assertEqual(result["memory_write_state"], "failed")
        self.assertIn("disk full", result["error"])

        mutation = get_mutation_record(self.tmp, result["mutation_id"])
        self.assertEqual(mutation["status"], "failed")
        self.assertIn("disk full", mutation["error"])

        events = list(root_path(self.tmp, "state_memory").rglob("*.json"))
        self.assertEqual(events, [])


if __name__ == "__main__":
    unittest.main()
