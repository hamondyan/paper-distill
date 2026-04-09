from __future__ import annotations

import json
import shutil
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from server.database import close_db
from server.memory_compile import compile_memory_views
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

        memory_state = read_memory_views(self.tmp)
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

    def test_append_memory_event_is_visible_on_snapshot_before_targeted_compile_applies(self) -> None:
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

        next_read = read_memory_views(self.tmp, view_keys=["taste"])
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

        self.assertFalse((root_path(self.tmp, "memory") / "assistant-brief.md").exists())
        brief_pending = list_uncompiled_memory_events(self.tmp, view_keys=["assistant-brief"])
        self.assertEqual(len(brief_pending), 1)
        self.assertEqual(brief_pending[0]["event_id"], append_result["event_id"])

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

    def test_memory_compile_clears_overlay_after_publishing_current_view(self) -> None:
        append_memory_event(
            self.tmp,
            event={
                "event_type": "dialogue_capture",
                "view_keys": ["taste"],
                "trust_label": "user-stated",
                "summary": "User wants failure analysis to stay central during paper comparison.",
                "content": "Treat negative-result rigor as a leading signal.",
                "source": {"kind": "dialogue", "turn_id": "turn-4"},
            },
        )

        before_compile = read_memory_views(self.tmp)
        self.assertTrue(before_compile["overlay_applied"])
        self.assertEqual(before_compile["views"]["taste"]["overlay_count"], 1)
        self.assertEqual(before_compile["views"]["taste"]["body"], "")

        compile_result = compile_memory_views(self.tmp, view_keys=["taste"])
        self.assertTrue(compile_result["ok"])
        self.assertTrue(compile_result["compiled"])

        after_compile = read_memory_views(self.tmp, view_keys=["taste"])
        self.assertFalse(after_compile["overlay_applied"])
        self.assertEqual(after_compile["views"]["taste"]["overlay_count"], 0)
        self.assertIn(
            "failure analysis to stay central",
            after_compile["views"]["taste"]["body"],
        )

    def test_view_scoped_read_triggers_opportunistic_compile_after_snapshot(self) -> None:
        append_memory_event(
            self.tmp,
            event={
                "event_type": "dialogue_capture",
                "view_keys": ["taste", "assistant-brief"],
                "trust_label": "user-stated",
                "summary": "User wants failure analysis to dominate quick paper triage.",
                "content": "Keep the assistant brief narrow, but compile taste now.",
                "source": {"kind": "dialogue", "turn_id": "turn-5"},
            },
        )

        state = read_memory_views(self.tmp, view_keys=["taste"])

        self.assertTrue(state["overlay_applied"])
        self.assertEqual(state["uncompiled_event_count"], 1)
        self.assertEqual(state["views"]["taste"]["body"], "")
        self.assertEqual(state["views"]["taste"]["overlay_count"], 1)
        self.assertEqual(
            state["views"]["taste"]["overlay_events"][0]["summary"],
            "User wants failure analysis to dominate quick paper triage.",
        )

        taste_pending = list_uncompiled_memory_events(self.tmp, view_keys=["taste"])
        brief_pending = list_uncompiled_memory_events(self.tmp, view_keys=["assistant-brief"])
        self.assertEqual(taste_pending, [])
        self.assertEqual(len(brief_pending), 1)
        self.assertEqual(brief_pending[0]["compile_status"], "partial")

        compiled_taste = read_memory_views(self.tmp, view_keys=["taste"])
        self.assertFalse(compiled_taste["overlay_applied"])
        self.assertIn(
            "failure analysis to dominate quick paper triage",
            compiled_taste["views"]["taste"]["body"],
        )

    def test_view_scoped_read_compile_failure_keeps_overlay_and_previous_view(self) -> None:
        write_markdown(
            root_path(self.tmp, "memory") / "taste.md",
            {"view_key": "taste", "compiled_at": "2026-04-09T10:30:00"},
            "# Taste\n\nCompiled memory says grounded evidence matters.",
        )
        append_memory_event(
            self.tmp,
            event={
                "event_type": "dialogue_capture",
                "view_keys": ["taste"],
                "trust_label": "user-stated",
                "summary": "User also wants negative results to stay central.",
                "source": {"kind": "dialogue", "turn_id": "turn-6"},
            },
        )

        with patch("server.memory_compile.apply_staged_bundle", side_effect=RuntimeError("publish broke")):
            state = read_memory_views(self.tmp, view_keys=["taste"])

        self.assertTrue(state["overlay_applied"])
        self.assertEqual(state["views"]["taste"]["overlay_count"], 1)
        self.assertIn("grounded evidence matters", state["views"]["taste"]["body"])
        self.assertEqual(
            state["views"]["taste"]["overlay_events"][0]["summary"],
            "User also wants negative results to stay central.",
        )

        pending = list_uncompiled_memory_events(self.tmp, view_keys=["taste"])
        self.assertEqual(len(pending), 1)
        self.assertEqual(pending[0]["compile_status"], "pending")

        visible_taste = (root_path(self.tmp, "memory") / "taste.md").read_text(encoding="utf-8")
        self.assertIn("grounded evidence matters", visible_taste)
        self.assertNotIn("negative results", visible_taste)

    def test_broad_read_does_not_trigger_opportunistic_compile(self) -> None:
        append_memory_event(
            self.tmp,
            event={
                "event_type": "dialogue_capture",
                "view_keys": ["taste"],
                "trust_label": "user-stated",
                "summary": "User prefers grounded robotics evaluations.",
                "source": {"kind": "dialogue", "turn_id": "turn-7"},
            },
        )

        with patch("server.memory_compile.compile_memory_views") as compile_mock:
            state = read_memory_views(self.tmp)

        compile_mock.assert_not_called()
        self.assertTrue(state["overlay_applied"])
        self.assertEqual(state["uncompiled_event_count"], 1)
        self.assertFalse((root_path(self.tmp, "memory") / "taste.md").exists())
        self.assertEqual(len(list_uncompiled_memory_events(self.tmp, view_keys=["taste"])), 1)

    def test_view_scoped_read_without_pending_events_does_not_trigger_compile(self) -> None:
        write_markdown(
            root_path(self.tmp, "memory") / "taste.md",
            {"view_key": "taste", "compiled_at": "2026-04-09T11:00:00"},
            "# Taste\n\nCompiled memory says grounded robotics evidence matters.",
        )

        with patch("server.memory_compile.compile_memory_views") as compile_mock:
            state = read_memory_views(self.tmp, view_keys=["taste"])

        compile_mock.assert_not_called()
        self.assertFalse(state["overlay_applied"])
        self.assertEqual(state["uncompiled_event_count"], 0)
        self.assertIn("grounded robotics evidence", state["views"]["taste"]["body"])


if __name__ == "__main__":
    unittest.main()
