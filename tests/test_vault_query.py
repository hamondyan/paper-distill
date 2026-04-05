from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from server.server import _load_candidate_sections
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

    def test_ensure_vault_structure_creates_daily_log_index(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = ensure_vault_structure(tmpdir)
            self.assertTrue((root / "daily-log" / "_index.md").exists())
            self.assertTrue((root / "raw" / "source" / "_index.md").exists())
            self.assertTrue((root / "raw" / "notes" / "_index.md").exists())
            self.assertTrue((root / "zotero" / "_index.md").exists())
            self.assertTrue((root / "zotero" / "imports" / "_index.md").exists())

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
            source_dir = vault / "Paper Distill" / "raw" / "source" / "2026-04-05"
            notes_dir = vault / "Paper Distill" / "raw" / "notes" / "2026-04-05"
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
            write_markdown(
                legacy_raw_dir / "legacy.md",
                {"paper_id": "doi:legacy", "compiled": False, "title": "Legacy"},
                "# Legacy",
            )

            raw_source = query_vault_sync(tmpdir, section="raw_source")
            raw_notes = query_vault_sync(tmpdir, section="raw_notes")
            raw_alias = query_vault_sync(tmpdir, section="raw")

            self.assertEqual(raw_source["stats"]["raw_source"], 1)
            self.assertEqual(raw_notes["stats"]["raw_notes"], 1)
            self.assertEqual(raw_notes["sections"]["raw_notes"][0]["title"], "Note")
            self.assertEqual(raw_alias["stats"]["raw"], 2)
            titles = {item["title"] for item in raw_alias["sections"]["raw"]}
            self.assertEqual(titles, {"Note", "Legacy"})
