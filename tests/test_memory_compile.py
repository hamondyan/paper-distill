from __future__ import annotations

import json
import shutil
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import yaml

from server.database import close_db
from server.memory_compile import compile_memory_views
from server.memory_promotion import promote_memory_event
from server.memory_runtime import append_memory_event, list_uncompiled_memory_events, read_memory_views
from server.vault_contract import root_path
from server.vault_ops import ensure_vault_structure, write_markdown


def _read_frontmatter(path: Path) -> dict:
    content = path.read_text(encoding="utf-8")
    _, remainder = content.split("---\n", 1)
    fm_text, _ = remainder.split("\n---\n", 1)
    return yaml.safe_load(fm_text) or {}


def _append_event_at(vault_path: str, *, now_iso: str, event: dict) -> dict:
    with patch("server.memory_runtime._now_iso", return_value=now_iso):
        result = append_memory_event(vault_path, event=event)
    assert result["ok"], result
    return result


def _promote_event_at(vault_path: str, *, now_iso: str, source_event_id: str) -> dict:
    with patch("server.memory_promotion._now_iso", return_value=now_iso):
        result = promote_memory_event(
            vault_path,
            source_event_id=source_event_id,
            decision_note="Confirmed in consolidation test.",
        )
    assert result["ok"], result
    return result


class MemoryCompileTest(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.mkdtemp()
        ensure_vault_structure(self.tmp)

    def tearDown(self) -> None:
        close_db(self.tmp)
        shutil.rmtree(self.tmp)

    def test_compile_pending_events_into_view_and_mark_events_compiled(self) -> None:
        append_result = append_memory_event(
            self.tmp,
            event={
                "event_type": "dialogue_capture",
                "view_keys": ["taste"],
                "trust_label": "user-stated",
                "summary": "User prefers grounded robotics results over benchmark-only deltas.",
                "content": "Prefer evaluations with explicit failure analysis.",
                "source": {"kind": "dialogue", "turn_id": "turn-1"},
            },
        )

        result = compile_memory_views(self.tmp, view_keys=["taste"])
        self.assertTrue(result["ok"])
        self.assertTrue(result["compiled"])
        self.assertEqual(result["compiled_view_keys"], ["taste"])
        self.assertEqual(result["compiled_event_count"], 1)

        taste_path = root_path(self.tmp, "memory") / "taste.md"
        self.assertTrue(taste_path.exists())
        compiled_text = taste_path.read_text(encoding="utf-8")
        self.assertIn("# Taste", compiled_text)
        self.assertIn("grounded robotics results", compiled_text)

        pending = list_uncompiled_memory_events(self.tmp, view_keys=["taste"])
        self.assertEqual(pending, [])

        memory_state = read_memory_views(self.tmp, view_keys=["taste"])
        self.assertFalse(memory_state["overlay_applied"])
        self.assertEqual(memory_state["uncompiled_event_count"], 0)
        self.assertEqual(memory_state["views"]["taste"]["overlay_count"], 0)
        self.assertIn("grounded robotics results", memory_state["views"]["taste"]["body"])

        event_path = Path(append_result["event_path"])
        event = json.loads(event_path.read_text(encoding="utf-8"))
        self.assertEqual(event["compile_status"], "compiled")
        self.assertEqual(event["compiled_view_keys"], ["taste"])
        self.assertIsNotNone(event["compiled_at"])

    def test_compile_multiple_view_keys_atomically(self) -> None:
        append_result = append_memory_event(
            self.tmp,
            event={
                "event_type": "dialogue_capture",
                "view_keys": ["taste", "assistant-brief"],
                "trust_label": "user-stated",
                "summary": "User values explicit failure analysis before leaderboard gains.",
                "content": "Prioritize papers that explain why systems fail.",
                "source": {"kind": "dialogue", "turn_id": "turn-2"},
            },
        )

        result = compile_memory_views(self.tmp, view_keys=["taste", "assistant-brief"])
        self.assertTrue(result["ok"])
        self.assertTrue(result["compiled"])
        self.assertEqual(result["compiled_view_keys"], ["assistant-brief", "taste"])
        self.assertEqual(result["compiled_event_count"], 1)

        taste_path = root_path(self.tmp, "memory") / "taste.md"
        brief_path = root_path(self.tmp, "memory") / "assistant-brief.md"
        self.assertTrue(taste_path.exists())
        self.assertTrue(brief_path.exists())
        self.assertIn("failure analysis", taste_path.read_text(encoding="utf-8"))
        self.assertIn("failure analysis", brief_path.read_text(encoding="utf-8"))

        event = json.loads(Path(append_result["event_path"]).read_text(encoding="utf-8"))
        self.assertEqual(event["compile_status"], "compiled")
        self.assertEqual(event["compiled_view_keys"], ["assistant-brief", "taste"])

    def test_compile_failure_keeps_previous_view_and_pending_events(self) -> None:
        write_markdown(
            root_path(self.tmp, "memory") / "taste.md",
            {"view_key": "taste", "compiled_at": "2026-04-09T09:30:00"},
            "# Taste\n\nCompiled memory says grounded evidence matters.",
        )
        append_result = append_memory_event(
            self.tmp,
            event={
                "event_type": "dialogue_capture",
                "view_keys": ["taste"],
                "trust_label": "user-stated",
                "summary": "User also wants negative results to remain first-class.",
                "source": {"kind": "dialogue", "turn_id": "turn-3"},
            },
        )

        with patch("server.memory_compile._apply_memory_compile_bundle", side_effect=RuntimeError("publish broke")):
            result = compile_memory_views(self.tmp, view_keys=["taste"])

        self.assertFalse(result["ok"])
        self.assertFalse(result["compiled"])
        self.assertIn("publish broke", result["error"])

        taste_text = (root_path(self.tmp, "memory") / "taste.md").read_text(encoding="utf-8")
        self.assertIn("grounded evidence matters", taste_text)
        self.assertNotIn("negative results", taste_text)

        pending = list_uncompiled_memory_events(self.tmp, view_keys=["taste"])
        self.assertEqual(len(pending), 1)
        self.assertEqual(pending[0]["event_id"], append_result["event_id"])
        self.assertEqual(pending[0]["compile_status"], "pending")

    def test_partial_compile_only_clears_overlay_for_compiled_view_keys(self) -> None:
        append_result = append_memory_event(
            self.tmp,
            event={
                "event_type": "dialogue_capture",
                "view_keys": ["taste", "assistant-brief"],
                "trust_label": "user-stated",
                "summary": "User wants failure analysis to dominate quick paper triage.",
                "content": "Use assistant brief for near-term reminders, but keep taste explicit.",
                "source": {"kind": "dialogue", "turn_id": "turn-4"},
            },
        )

        result = compile_memory_views(self.tmp, view_keys=["taste"])
        self.assertTrue(result["ok"])
        self.assertEqual(result["compiled_view_keys"], ["taste"])

        taste_pending = list_uncompiled_memory_events(self.tmp, view_keys=["taste"])
        brief_pending = list_uncompiled_memory_events(self.tmp, view_keys=["assistant-brief"])
        self.assertEqual(taste_pending, [])
        self.assertEqual(len(brief_pending), 1)
        self.assertEqual(brief_pending[0]["event_id"], append_result["event_id"])
        self.assertEqual(brief_pending[0]["compile_status"], "partial")

        state = read_memory_views(self.tmp, view_keys=["taste", "assistant-brief"])
        self.assertEqual(state["views"]["taste"]["overlay_count"], 0)
        self.assertEqual(state["views"]["assistant-brief"]["overlay_count"], 1)
        self.assertIn("failure analysis to dominate", state["views"]["taste"]["body"])
        self.assertEqual(state["views"]["assistant-brief"]["body"], "")

    def test_compile_noop_when_no_pending_events(self) -> None:
        result = compile_memory_views(self.tmp, view_keys=["taste"])

        self.assertTrue(result["ok"])
        self.assertFalse(result["compiled"])
        self.assertEqual(result["compiled_view_keys"], [])
        self.assertEqual(result["compiled_event_count"], 0)
        self.assertEqual(result["reason"], "no_pending_events")
        self.assertFalse((root_path(self.tmp, "memory") / "taste.md").exists())

    def test_compile_active_threads_keeps_only_latest_active_threads(self) -> None:
        append_memory_event(
            self.tmp,
            event={
                "event_type": "thread_update",
                "view_keys": ["active-threads"],
                "trust_label": "jointly-derived",
                "status": "confirmed",
                "summary": "Failure-aware embodied planning is an active workstream.",
                "content": "Track papers and ideas around explicit failure recovery loops.",
                "metadata": {
                    "thread_id": "failure-aware-planning",
                    "thread_action": "enter",
                    "thread_title": "Failure-Aware Planning",
                },
            },
        )
        append_memory_event(
            self.tmp,
            event={
                "event_type": "thread_update",
                "view_keys": ["active-threads"],
                "trust_label": "jointly-derived",
                "status": "confirmed",
                "summary": "Manipulation benchmarks thread is active while we compare tasks.",
                "metadata": {
                    "thread_id": "manipulation-benchmarks",
                    "thread_action": "enter",
                    "thread_title": "Manipulation Benchmarks",
                },
            },
        )
        append_memory_event(
            self.tmp,
            event={
                "event_type": "thread_update",
                "view_keys": ["active-threads"],
                "trust_label": "jointly-derived",
                "status": "confirmed",
                "summary": "We narrowed the planning thread toward recovery-heavy tasks.",
                "metadata": {
                    "thread_id": "failure-aware-planning",
                    "thread_action": "update",
                    "thread_title": "Failure-Aware Planning",
                },
            },
        )
        append_memory_event(
            self.tmp,
            event={
                "event_type": "thread_update",
                "view_keys": ["active-threads"],
                "trust_label": "jointly-derived",
                "status": "retired",
                "summary": "Manipulation benchmarks thread is no longer active.",
                "metadata": {
                    "thread_id": "manipulation-benchmarks",
                    "thread_action": "exit",
                    "thread_title": "Manipulation Benchmarks",
                },
            },
        )

        result = compile_memory_views(self.tmp, view_keys=["active-threads"])
        self.assertTrue(result["ok"])
        self.assertEqual(result["compiled_view_keys"], ["active-threads"])
        self.assertEqual(result["compiled_event_count"], 4)

        active_threads_path = root_path(self.tmp, "memory") / "active-threads.md"
        compiled_text = active_threads_path.read_text(encoding="utf-8")
        frontmatter = _read_frontmatter(active_threads_path)

        self.assertEqual(frontmatter["active_thread_count"], 1)
        self.assertEqual(frontmatter["inactive_thread_count"], 1)
        self.assertIn("## Current Active Threads", compiled_text)
        self.assertIn("### Failure-Aware Planning", compiled_text)
        self.assertIn("Lifecycle: active (update)", compiled_text)
        self.assertIn("Recent updates:", compiled_text)
        self.assertIn("Manipulation Benchmarks", compiled_text)
        self.assertIn("Recently Closed or Dormant", compiled_text)

    def test_compile_active_threads_stale_thread_drops_from_active_list(self) -> None:
        append_memory_event(
            self.tmp,
            event={
                "event_type": "thread_update",
                "view_keys": ["active-threads"],
                "trust_label": "jointly-derived",
                "status": "confirmed",
                "summary": "Cross-embodiment transfer is an active thread.",
                "metadata": {
                    "thread_id": "cross-embodiment-transfer",
                    "thread_action": "enter",
                    "thread_title": "Cross-Embodiment Transfer",
                },
            },
        )
        append_memory_event(
            self.tmp,
            event={
                "event_type": "thread_update",
                "view_keys": ["active-threads"],
                "trust_label": "jointly-derived",
                "status": "stale",
                "summary": "Cross-embodiment transfer is dormant until new evidence arrives.",
                "metadata": {
                    "thread_id": "cross-embodiment-transfer",
                    "thread_action": "update",
                    "thread_title": "Cross-Embodiment Transfer",
                },
            },
        )

        result = compile_memory_views(self.tmp, view_keys=["active-threads"])
        self.assertTrue(result["ok"])

        active_threads_path = root_path(self.tmp, "memory") / "active-threads.md"
        compiled_text = active_threads_path.read_text(encoding="utf-8")
        frontmatter = _read_frontmatter(active_threads_path)
        self.assertEqual(frontmatter["active_thread_count"], 0)
        self.assertEqual(frontmatter["inactive_thread_count"], 1)
        self.assertIn("No threads are currently active", compiled_text)
        self.assertIn("Cross-Embodiment Transfer", compiled_text)

    def test_compile_consolidates_duplicate_taste_memory_into_one_current_signal(self) -> None:
        first = _append_event_at(
            self.tmp,
            now_iso="2026-01-10T09:00:00+00:00",
            event={
                "event_type": "preference_update",
                "view_keys": ["taste"],
                "trust_label": "user-stated",
                "status": "provisional",
                "summary": "Failure analysis should dominate taste memory for ranking.",
                "content": "Prefer grounded failure analysis before leaderboard gains.",
                "metadata": {
                    "preferred_venues": ["CoRL"],
                    "accepted_keywords": ["failure analysis"],
                },
            },
        )
        _promote_event_at(
            self.tmp,
            now_iso="2026-01-10T09:10:00+00:00",
            source_event_id=first["event_id"],
        )

        second = _append_event_at(
            self.tmp,
            now_iso="2026-01-12T12:00:00+00:00",
            event={
                "event_type": "preference_update",
                "view_keys": ["taste"],
                "trust_label": "user-stated",
                "status": "provisional",
                "summary": "Grounded failure analysis should stay ahead of benchmark deltas.",
                "content": "Prefer grounded failure analysis before benchmark deltas.",
                "metadata": {
                    "preferred_venues": ["CoRL"],
                    "accepted_keywords": ["failure analysis"],
                },
            },
        )
        _promote_event_at(
            self.tmp,
            now_iso="2026-01-12T12:10:00+00:00",
            source_event_id=second["event_id"],
        )

        result = compile_memory_views(self.tmp, view_keys=["taste"])
        self.assertTrue(result["ok"])

        taste_path = root_path(self.tmp, "memory") / "taste.md"
        compiled_text = taste_path.read_text(encoding="utf-8")
        frontmatter = _read_frontmatter(taste_path)

        self.assertEqual(frontmatter["compiled_item_count"], 1)
        self.assertIn("| consolidated |", compiled_text)
        self.assertIn("support=2", compiled_text)
        self.assertEqual(
            compiled_text.count("Prefer grounded failure analysis before"),
            1,
        )

    def test_compile_decays_old_memory_into_stale_and_retired(self) -> None:
        stale_source = _append_event_at(
            self.tmp,
            now_iso="2025-10-01T09:00:00+00:00",
            event={
                "event_type": "preference_update",
                "view_keys": ["taste"],
                "trust_label": "user-stated",
                "status": "provisional",
                "summary": "Occlusion-heavy failure analysis used to dominate ranking.",
                "content": "Favor occlusion-heavy failure analyses first.",
                "metadata": {
                    "preferred_venues": ["CoRL"],
                    "accepted_keywords": ["occlusion"],
                },
            },
        )
        _promote_event_at(
            self.tmp,
            now_iso="2025-10-01T09:10:00+00:00",
            source_event_id=stale_source["event_id"],
        )

        retired_source = _append_event_at(
            self.tmp,
            now_iso="2024-01-15T09:00:00+00:00",
            event={
                "event_type": "profile_update",
                "view_keys": ["profile"],
                "trust_label": "user-stated",
                "status": "provisional",
                "summary": "Very old profile direction for a completed project.",
                "content": "Finished project context that should no longer drive retrieval.",
                "metadata": {
                    "direction": "Completed old project direction.",
                    "seed_papers": ["10.48550/arxiv.old"],
                },
            },
        )
        _promote_event_at(
            self.tmp,
            now_iso="2024-01-15T09:10:00+00:00",
            source_event_id=retired_source["event_id"],
        )

        taste_result = compile_memory_views(self.tmp, view_keys=["taste"])
        profile_result = compile_memory_views(self.tmp, view_keys=["profile"])
        self.assertTrue(taste_result["ok"])
        self.assertTrue(profile_result["ok"])

        taste_text = (root_path(self.tmp, "memory") / "taste.md").read_text(encoding="utf-8")
        profile_text = (root_path(self.tmp, "memory") / "profile.md").read_text(encoding="utf-8")
        self.assertIn("| stale |", taste_text)
        self.assertIn("Lower-Salience Memory", taste_text)
        self.assertIn("| retired |", profile_text)


if __name__ == "__main__":
    unittest.main()
