from __future__ import annotations

import os
import shutil
import tempfile
import unittest

from server.database import close_db, get_db


class DatabaseSchemaTest(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.mkdtemp()
        self.db_path = os.path.join(
            self.tmp,
            "Paper Distill",
            ".state",
            "paper-distill.db",
        )
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)

    def tearDown(self) -> None:
        close_db(self.tmp)
        shutil.rmtree(self.tmp)

    def test_compile_deps_schema_allows_paper_dependencies(self) -> None:
        conn = get_db(self.tmp)
        table_sql = conn.execute(
            """
            SELECT sql
            FROM sqlite_master
            WHERE type = 'table' AND name = 'compile_deps'
            """
        ).fetchone()["sql"]
        self.assertNotIn("REFERENCES concept_registry", table_sql)

        conn.execute(
            """
            INSERT INTO compile_state
                (page_id, page_type, compile_version, schema_version, compiled_at)
            VALUES
                ('query-a', 'query', 1, 'current', '2026-04-09T00:00:00'),
                ('paper-a', 'paper', 1, 'current', '2026-04-09T00:00:00')
            """
        )
        conn.execute(
            """
            INSERT INTO compile_deps
                (page_id, page_type, dep_type, dep_id, dep_version)
            VALUES
                ('query-a', 'query', 'paper', 'paper-a', 1)
            """
        )
        conn.commit()

        row = conn.execute(
            """
            SELECT dep_type, dep_id
            FROM compile_deps
            WHERE page_id = 'query-a' AND page_type = 'query'
            """
        ).fetchone()
        self.assertIsNotNone(row)
        self.assertEqual(row["dep_type"], "paper")
        self.assertEqual(row["dep_id"], "paper-a")

        unique_index = conn.execute(
            """
            SELECT name
            FROM sqlite_master
            WHERE type = 'index' AND name = 'idx_compile_deps_unique'
            """
        ).fetchone()
        self.assertIsNotNone(unique_index)


if __name__ == "__main__":
    unittest.main()
