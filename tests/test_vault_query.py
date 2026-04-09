from __future__ import annotations

import tempfile
import unittest
from datetime import datetime, timedelta
from pathlib import Path

from server.server import _load_candidate_sections
from server.vault_contract import LegacyTaxonomyWriteError
from server.vault_ops import ensure_vault_structure, write_markdown
from server.vault_query import query_vault_sync


class VaultQueryTest(unittest.TestCase):
    def test_load_candidate_sections_recovers_body_fields(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            note = Path(tmpdir) / "Paper Distill" / "inbox" / "2026-04-04" / "paper.md"
            note.parent.mkdir(parents=True, exist_ok=True)
            note.write_text(
                """---
paper_id: doi:test
status: proposed
---

# Example

## Summary

Short summary.

## Abstract

Longer abstract.

## Why Recommended

Because it matches the topic.

## Links

- Open access: https://example.com/paper.pdf
""",
                encoding="utf-8",
            )

            sections = _load_candidate_sections(
                tmpdir,
                "Paper Distill/inbox/2026-04-04/paper.md",
            )
            self.assertEqual(sections["summary"], "Short summary.")
            self.assertEqual(sections["abstract"], "Longer abstract.")
            self.assertEqual(sections["why_recommended"], "Because it matches the topic.")
            self.assertEqual(sections["open_access_url"], "https://example.com/paper.pdf")

    def test_ensure_vault_structure_creates_taxonomy_indexes(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = ensure_vault_structure(tmpdir)
            self.assertTrue((root / "sources" / "evidence" / "_index.md").exists())
            self.assertTrue((root / "sources" / "notes" / "_index.md").exists())
            self.assertTrue((root / "insights" / "digests" / "_index.md").exists())
            self.assertTrue((root / "insights" / "queries" / "_index.md").exists())
            self.assertTrue((root / "memory" / "_index.md").exists())
            self.assertTrue((root / "zotero" / "_index.md").exists())
            self.assertTrue((root / "zotero" / "imports" / "_index.md").exists())
            self.assertTrue((root / "index.md").exists())
            self.assertTrue((root / "log.md").exists())

    def test_query_vault_filters_inbox_status(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            vault = Path(tmpdir)
            inbox_dir = vault / "Paper Distill" / "inbox" / "2026-04-04"
            inbox_dir.mkdir(parents=True, exist_ok=True)

            write_markdown(
                inbox_dir / "paper-a.md",
                {
                    "paper_id": "doi:one",
                    "status": "approved",
                    "title": "Paper A",
                    "matched_topics": ["vision-language-action"],
                },
                "# Paper A",
            )
            write_markdown(
                inbox_dir / "paper-b.md",
                {
                    "paper_id": "doi:two",
                    "status": "proposed",
                    "title": "Paper B",
                    "matched_topics": ["manipulation"],
                },
                "# Paper B",
            )

            data = query_vault_sync(tmpdir, section="inbox", status="approved")
            self.assertEqual(data["stats"]["inbox"], 1)
            self.assertEqual(data["sections"]["inbox"][0]["paper_id"], "doi:one")

    def test_query_vault_separates_raw_source_and_raw_notes(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            vault = Path(tmpdir)
            source_dir = vault / "Paper Distill" / "sources" / "evidence" / "2026-04-05"
            notes_dir = vault / "Paper Distill" / "sources" / "notes" / "2026-04-05"
            legacy_raw_dir = vault / "Paper Distill" / "raw" / "2026-04-05"
            source_dir.mkdir(parents=True, exist_ok=True)
            notes_dir.mkdir(parents=True, exist_ok=True)
            legacy_raw_dir.mkdir(parents=True, exist_ok=True)

            write_markdown(
                source_dir / "paper-source.md",
                {"paper_id": "arxiv:2501.00001", "compiled": False, "title": "Source"},
                "# Source",
            )
            write_markdown(
                notes_dir / "paper-note.md",
                {"paper_id": "arxiv:2501.00001", "compiled": False, "title": "Note"},
                "# Note",
            )
            (legacy_raw_dir / "legacy.md").write_text(
                "---\npaper_id: doi:legacy\ncompiled: false\ntitle: Legacy\n---\n\n# Legacy\n",
                encoding="utf-8",
            )

            raw_source = query_vault_sync(tmpdir, section="raw_source")
            raw_notes = query_vault_sync(tmpdir, section="raw_notes")
            raw_alias = query_vault_sync(tmpdir, section="raw")
            canonical_notes = query_vault_sync(tmpdir, section="source_notes")

            self.assertEqual(raw_source["stats"]["raw_source"], 1)
            self.assertEqual(raw_notes["stats"]["raw_notes"], 1)
            self.assertEqual(raw_notes["sections"]["raw_notes"][0]["title"], "Note")
            self.assertEqual(raw_alias["stats"]["raw"], 1)
            self.assertEqual(canonical_notes["stats"]["source_notes"], 1)
            titles = {item["title"] for item in raw_alias["sections"]["raw"]}
            self.assertEqual(titles, {"Note"})

    def test_write_markdown_rejects_legacy_raw_root(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            with self.assertRaises(LegacyTaxonomyWriteError):
                write_markdown(
                    Path(tmpdir) / "Paper Distill" / "raw" / "notes" / "2026-04-05" / "legacy.md",
                    {"paper_id": "doi:legacy", "compiled": False},
                    "# Legacy",
                )

    def test_query_vault_days_back_uses_best_available_timestamp_by_default(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            vault = Path(tmpdir)
            inbox_dir = vault / "Paper Distill" / "inbox" / "2026-04-04"
            inbox_dir.mkdir(parents=True, exist_ok=True)
            now = datetime.now()

            write_markdown(
                inbox_dir / "old-paper.md",
                {
                    "paper_id": "doi:old",
                    "status": "proposed",
                    "title": "Old Paper",
                    "retrieved_at": (now - timedelta(days=30)).isoformat(),
                },
                "# Old Paper",
            )
            write_markdown(
                inbox_dir / "new-paper.md",
                {
                    "paper_id": "doi:new",
                    "status": "proposed",
                    "title": "New Paper",
                    "retrieved_at": (now - timedelta(days=1)).isoformat(),
                },
                "# New Paper",
            )

            data = query_vault_sync(tmpdir, section="inbox", days_back=7)

            self.assertEqual(data["stats"]["inbox"], 1)
            self.assertEqual(data["sections"]["inbox"][0]["title"], "New Paper")
