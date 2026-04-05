from __future__ import annotations

import asyncio
import json
import tempfile
import unittest
from pathlib import Path

from server.zotero.client import add_papers, search_papers


class ZoteroClientTest(unittest.TestCase):
    def test_add_papers_local_first_writes_csl_json_import_pack(self) -> None:
        paper = {
            "title": "A Local-First VLA Paper",
            "authors": ["Jane Doe", "Alex Smith"],
            "year": 2026,
            "doi": "10.1000/local-first",
            "abstract": "A paper used to validate local-first Zotero exports.",
            "venue": "ICRA 2026",
            "topic_tags": ["vision-language-action", "manipulation"],
            "citekey": "doe2026-local",
            "arxiv_id": "2601.00001",
        }

        with tempfile.TemporaryDirectory() as tmpdir:
            exported = asyncio.run(
                add_papers(
                    [paper],
                    mode="local_first",
                    export_dir=tmpdir,
                )
            )

            self.assertEqual(exported[0]["zotero_status"], "local_exported")
            export_path = Path(exported[0]["zotero_import_path"])
            self.assertTrue(export_path.exists())
            payload = json.loads(export_path.read_text(encoding="utf-8"))
            self.assertEqual(payload[0]["title"], paper["title"])
            self.assertEqual(payload[0]["DOI"], paper["doi"])
            self.assertEqual(payload[0]["container-title"], paper["venue"])

    def test_search_papers_reports_unavailable_outside_web_api_mode(self) -> None:
        results = asyncio.run(search_papers("vla", mode="local_first"))
        self.assertIn("unavailable", results[0]["error"])
