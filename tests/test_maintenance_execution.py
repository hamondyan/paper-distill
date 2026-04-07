from __future__ import annotations

import json
import os
import shutil
import tempfile
import unittest

from server.concept_registry import get_concept, register_concept, promote_concept
from server.database import close_db, get_db
from server.maintenance import confirm_task, execute_merge, execute_promote, execute_refresh


class MaintenanceExecutionTest(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.mkdtemp()
        pd_root = os.path.join(self.tmp, "Paper Distill")
        for d in [".state", "wiki/papers", "wiki/concepts", "wiki/topics", "compiled_ir"]:
            os.makedirs(os.path.join(pd_root, d), exist_ok=True)
        get_db(self.tmp)

    def tearDown(self) -> None:
        close_db(self.tmp)
        shutil.rmtree(self.tmp)

    def _insert_task(self, task_type: str, payload: dict, status: str = "confirmed") -> int:
        conn = get_db(self.tmp)
        cur = conn.execute(
            """INSERT INTO maintenance_queue
               (task_type, payload, confidence, status, created_at)
               VALUES (?, ?, 1.0, ?, '2026-04-06T00:00:00')""",
            (task_type, json.dumps(payload), status),
        )
        conn.commit()
        return cur.lastrowid

    def test_execute_merge_is_idempotent(self) -> None:
        register_concept(self.tmp, "Concept A")
        register_concept(self.tmp, "Concept B")
        task_id = self._insert_task(
            "merge_candidate",
            {"from_id": "concept-a", "to_id": "concept-b", "reason": "test"},
        )

        first = execute_merge(self.tmp, task_id)
        second = execute_merge(self.tmp, task_id)

        self.assertTrue(first.get("merged") or first.get("completed"))
        self.assertTrue(second.get("already_applied") or second.get("completed"))
        resolved = get_concept(self.tmp, "concept-b")
        self.assertIsNotNone(resolved)
        self.assertIsNone(get_concept(self.tmp, "concept-a"))

    def test_execute_promote_is_idempotent(self) -> None:
        register_concept(self.tmp, "Diffusion Policy")
        concept_path = os.path.join(self.tmp, "Paper Distill", "wiki", "concepts", "diffusion-policy.md")
        with open(concept_path, "w", encoding="utf-8") as f:
            f.write("---\nconcept: Diffusion Policy\n---\n\n# Diffusion Policy\n")
        task_id = self._insert_task(
            "promote_to_topic",
            {"concept": "diffusion-policy", "paper_count": 5},
        )

        first = execute_promote(self.tmp, task_id)
        second = execute_promote(self.tmp, task_id)

        self.assertTrue(first.get("promoted") or first.get("completed"))
        self.assertTrue(second.get("already_applied") or second.get("completed"))
        concept = get_concept(self.tmp, "diffusion-policy")
        self.assertIsNotNone(concept)
        self.assertEqual(concept["type"], "topic")
        self.assertTrue(
            os.path.exists(os.path.join(self.tmp, "Paper Distill", "wiki", "topics", "diffusion-policy.md"))
        )

    def test_execute_refresh_marks_missing_topic_blocked(self) -> None:
        task_id = self._insert_task(
            "stale_topic_refresh",
            {"topic": "robotics", "new_paper_count": 3, "reasons": ["3 new papers"]},
        )
        result = execute_refresh(self.tmp, task_id)
        self.assertTrue(result.get("blocked") or result.get("error"))

    def test_execute_refresh_updates_existing_topic_page(self) -> None:
        register_concept(self.tmp, "robotics", concept_type="topic")
        topic_path = os.path.join(self.tmp, "Paper Distill", "wiki", "topics", "robotics.md")
        with open(topic_path, "w", encoding="utf-8") as f:
            f.write("---\ntopic: robotics\n---\n\n## My Notes\n\nKeep me.\n")

        conn = get_db(self.tmp)
        conn.execute(
            """INSERT OR REPLACE INTO compile_state
               (page_id, page_type, compile_version, schema_version, compiled_at)
               VALUES ('paper-a', 'paper', 1, 'legacy', '2026-04-06T00:00:00')"""
        )
        conn.execute(
            """INSERT OR REPLACE INTO compile_deps
               (page_id, page_type, dep_type, dep_id, dep_version)
               VALUES ('paper-a', 'paper', 'topic', 'robotics', 1)"""
        )
        conn.commit()

        task_id = self._insert_task(
            "stale_topic_refresh",
            {"topic": "robotics", "new_paper_count": 3, "reasons": ["3 new papers"]},
        )
        result = execute_refresh(self.tmp, task_id)
        self.assertTrue(result.get("completed"))

        page = open(topic_path, "r", encoding="utf-8").read()
        self.assertIn("Representative Papers", page)
        self.assertIn("[[papers/paper-a]]", page)
        self.assertIn("## My Notes", page)
        self.assertIn("Keep me.", page)
