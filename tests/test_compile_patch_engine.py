from __future__ import annotations

import os
import shutil
import tempfile
import unittest

from server.compile_ir import commit_compile_result
from server.database import close_db, get_db


class CompilePatchEngineTest(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.mkdtemp()
        pd_root = os.path.join(self.tmp, "Paper Distill")
        for d in [".state", "wiki/papers", "wiki/topics", "compiled_ir"]:
            os.makedirs(os.path.join(pd_root, d), exist_ok=True)
        get_db(self.tmp)

    def tearDown(self) -> None:
        close_db(self.tmp)
        shutil.rmtree(self.tmp)

    def _read_page(self, rel_path: str) -> str:
        with open(os.path.join(self.tmp, "Paper Distill", rel_path), "r", encoding="utf-8") as f:
            return f.read()

    def test_commit_preserves_my_notes_on_update(self) -> None:
        first = """<!-- managed:start section=context -->
## Context
Old generated summary.
<!-- managed:end section=context -->

## My Notes

Keep this exactly.
"""
        second = """<!-- managed:start section=context -->
## Context
New generated summary.
<!-- managed:end section=context -->
"""

        commit_compile_result(
            self.tmp,
            "smith2024",
            "paper",
            first,
            {"citekey": "smith2024", "title": "A Paper", "compile_version": 1},
        )
        result = commit_compile_result(
            self.tmp,
            "smith2024",
            "paper",
            second,
            {"citekey": "smith2024", "title": "A Paper", "compile_version": 1},
        )

        self.assertTrue(result["written"])
        page = self._read_page("wiki/papers/smith2024.md")
        self.assertIn("New generated summary.", page)
        self.assertIn("## My Notes", page)
        self.assertIn("Keep this exactly.", page)
        self.assertNotIn("Old generated summary.", page)

    def test_commit_detects_conflict_when_managed_block_changed_by_user(self) -> None:
        original = """<!-- managed:start section=context -->
## Context
Original generated summary.
<!-- managed:end section=context -->
"""
        updated = """<!-- managed:start section=context -->
## Context
Fresh generated summary.
<!-- managed:end section=context -->
"""

        commit_compile_result(
            self.tmp,
            "jones2024",
            "paper",
            original,
            {"citekey": "jones2024", "title": "Another Paper", "compile_version": 1},
        )

        page_path = os.path.join(self.tmp, "Paper Distill", "wiki", "papers", "jones2024.md")
        current = open(page_path, "r", encoding="utf-8").read()
        with open(page_path, "w", encoding="utf-8") as f:
            f.write(current.replace("Original generated summary.", "User-edited summary."))

        result = commit_compile_result(
            self.tmp,
            "jones2024",
            "paper",
            updated,
            {"citekey": "jones2024", "title": "Another Paper", "compile_version": 1},
        )

        self.assertTrue(result.get("conflict_detected"))
        page = self._read_page("wiki/papers/jones2024.md")
        self.assertIn("User-edited summary.", page)
        self.assertNotIn("Fresh generated summary.", page)
