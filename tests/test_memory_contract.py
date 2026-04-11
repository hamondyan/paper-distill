from __future__ import annotations

import shutil
import tempfile
import unittest
from pathlib import Path

import yaml

from server.database import close_db
from server.memory_compile import compile_memory_views
from server.memory_contract import order_memory_view_keys, typed_memory_view_keys
from server.memory_runtime import append_memory_event, read_memory_views
from server.vault_contract import root_path
from server.vault_ops import ensure_vault_structure


def _read_frontmatter(path: Path) -> dict:
    content = path.read_text(encoding="utf-8")
    _, remainder = content.split("---\n", 1)
    fm_text, _ = remainder.split("\n---\n", 1)
    return yaml.safe_load(fm_text) or {}


class MemoryContractTest(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.mkdtemp()
        ensure_vault_structure(self.tmp)

    def tearDown(self) -> None:
        close_db(self.tmp)
        shutil.rmtree(self.tmp)

    def test_typed_memory_view_keys_are_locked(self) -> None:
        self.assertEqual(
            typed_memory_view_keys(),
            (
                "assistant-brief",
                "taste",
                "profile",
                "active-threads",
            ),
        )

    def test_order_memory_view_keys_prioritizes_assistant_brief(self) -> None:
        ordered = order_memory_view_keys(
            ["taste", "assistant-brief", "profile", "taste", "assistant-brief"]
        )
        self.assertEqual(ordered, ["assistant-brief", "taste", "profile"])

    def test_append_rejects_invalid_status_for_taste(self) -> None:
        result = append_memory_event(
            self.tmp,
            event={
                "event_type": "dialogue_capture",
                "view_keys": ["taste"],
                "trust_label": "user-stated",
                "status": "rejected",
                "summary": "User prefers grounded robotics results over benchmark-only gains.",
            },
        )

        self.assertFalse(result["ok"])
        self.assertIn("not allowed for view 'taste'", result["error"])

    def test_append_rejects_active_thread_without_thread_metadata(self) -> None:
        result = append_memory_event(
            self.tmp,
            event={
                "event_type": "thread_update",
                "view_keys": ["active-threads"],
                "trust_label": "jointly-derived",
                "status": "confirmed",
                "summary": "We are actively exploring failure-aware embodied planning.",
            },
        )

        self.assertFalse(result["ok"])
        self.assertIn("metadata.thread_id", result["error"])

    def test_compile_and_read_expose_typed_memory_contract_metadata(self) -> None:
        append_memory_event(
            self.tmp,
            event={
                "event_type": "dialogue_capture",
                "view_keys": ["taste", "assistant-brief"],
                "trust_label": "user-stated",
                "summary": "User wants failure analysis and negative results to dominate quick triage.",
                "content": "Read the assistant brief first, then fall through to taste.",
            },
        )

        result = compile_memory_views(self.tmp, view_keys=["taste", "assistant-brief"])
        self.assertTrue(result["ok"])
        self.assertEqual(result["compiled_view_keys"], ["assistant-brief", "taste"])

        brief_frontmatter = _read_frontmatter(root_path(self.tmp, "memory") / "assistant-brief.md")
        taste_frontmatter = _read_frontmatter(root_path(self.tmp, "memory") / "taste.md")
        self.assertEqual(brief_frontmatter["view_type"], "typed-memory-view")
        self.assertTrue(brief_frontmatter["summary_only"])
        self.assertEqual(brief_frontmatter["read_role"], "entrypoint-summary")
        self.assertEqual(taste_frontmatter["view_type"], "typed-memory-view")
        self.assertIn("dialogue_capture", taste_frontmatter["allowed_event_types"])
        self.assertIn("provisional", taste_frontmatter["allowed_statuses"])

        state = read_memory_views(self.tmp, view_keys=["taste", "assistant-brief"])
        self.assertEqual(list(state["views"].keys()), ["assistant-brief", "taste"])
        self.assertTrue(state["views"]["assistant-brief"]["contract"]["typed"])
        self.assertEqual(
            state["views"]["assistant-brief"]["contract"]["read_role"],
            "entrypoint-summary",
        )
        self.assertEqual(state["views"]["taste"]["contract"]["title"], "Taste")


if __name__ == "__main__":
    unittest.main()
