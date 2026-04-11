from __future__ import annotations

import shutil
import tempfile
import unittest
from pathlib import Path

import yaml

from server.database import close_db
from server.vault_contract import root_path
from server.vault_ops import (
    ensure_vault_structure,
    mark_inbox_capture_failed,
    promote_concept_page_to_topic_asset,
    rewrite_page_asset_links,
    write_markdown,
)


def _read_note(path: Path) -> tuple[dict, str]:
    content = path.read_text(encoding="utf-8")
    _, remainder = content.split("---\n", 1)
    fm_text, body = remainder.split("\n---\n", 1)
    return yaml.safe_load(fm_text) or {}, body.strip()


class AssetWriterTest(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.mkdtemp()
        ensure_vault_structure(self.tmp)

    def tearDown(self) -> None:
        close_db(self.tmp)
        shutil.rmtree(self.tmp)

    def test_rewrite_page_asset_links_updates_query_refs(self) -> None:
        note_path = root_path(self.tmp, "queries") / "merge-note.md"
        write_markdown(
            note_path,
            {
                "type": "comparison-note",
                "title": "Merge Note",
                "question": "How do these concepts compare?",
                "concepts_referenced": ["concept-a"],
                "topics_referenced": [],
                "promotion_targets": [{"page_type": "concept", "page_id": "concept-a"}],
            },
            "# Merge Note\n\n[[concepts/concept-a]]\n\n## My Notes\n\nKeep me.",
        )

        rewritten_path = rewrite_page_asset_links(
            self.tmp,
            "merge-note",
            "query",
            "concept-a",
            "concept-b",
        )

        self.assertEqual(rewritten_path, note_path)
        frontmatter, body = _read_note(note_path)
        self.assertEqual(frontmatter["concepts_referenced"], ["concept-b"])
        self.assertEqual(frontmatter["promotion_targets"][0]["page_id"], "concept-b")
        self.assertIn("[[concepts/concept-b]]", body)
        self.assertIn("## My Notes", body)
        self.assertIn("Keep me.", body)

    def test_promote_concept_page_to_topic_asset_creates_redirect_pair(self) -> None:
        concept_path = root_path(self.tmp, "concepts") / "diffusion-policy.md"
        write_markdown(
            concept_path,
            {"concept": "Diffusion Policy", "aliases": ["DP"]},
            "# Diffusion Policy\n\nOriginal body.",
        )

        result = promote_concept_page_to_topic_asset(self.tmp, "diffusion-policy")

        topic_path = root_path(self.tmp, "topics") / "diffusion-policy.md"
        self.assertEqual(result["topic_path"], str(topic_path))
        self.assertEqual(result["concept_path"], str(concept_path))
        topic_frontmatter, topic_body = _read_note(topic_path)
        concept_frontmatter, concept_body = _read_note(concept_path)
        self.assertEqual(topic_frontmatter["concept"], "Diffusion Policy")
        self.assertIn("Original body.", topic_body)
        self.assertEqual(concept_frontmatter["redirect_to"], "topics/diffusion-policy")
        self.assertIn("[[topics/diffusion-policy]]", concept_body)

    def test_mark_inbox_capture_failed_updates_existing_note(self) -> None:
        note_path = root_path(self.tmp, "inbox") / "2026-04-11" / "candidate.md"
        write_markdown(
            note_path,
            {
                "paper_id": "doi:test",
                "status": "proposed",
                "title": "Candidate",
                "capture_status": "pending",
                "capture_error": "",
                "canonical_html_url": "",
                "canonical_pdf_url": "",
            },
            "# Candidate",
        )

        updates = mark_inbox_capture_failed(
            note_path,
            error="capture exploded",
            canonical_html_url="https://example.com/paper",
            canonical_pdf_url="https://example.com/paper.pdf",
        )

        frontmatter, _ = _read_note(note_path)
        self.assertEqual(updates["capture_status"], "failed")
        self.assertEqual(frontmatter["capture_status"], "failed")
        self.assertEqual(frontmatter["capture_error"], "capture exploded")
        self.assertEqual(frontmatter["canonical_html_url"], "https://example.com/paper")
        self.assertEqual(frontmatter["canonical_pdf_url"], "https://example.com/paper.pdf")
