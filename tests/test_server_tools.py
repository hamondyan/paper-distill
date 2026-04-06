from __future__ import annotations

import asyncio
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import AsyncMock, patch

from server.arxiv_capture import CleanedArxivDocument
from server.config import load_settings
from server.server import (
    analyze_knowledge_graph,
    process_inbox,
    update_learned_preferences,
    upsert_wiki_article,
)
from server.vault_ops import ensure_vault_structure, write_markdown
from server.vault_query import query_vault_sync


def _fake_source_doc(title: str, abstract: str, capture_fidelity: str = "low") -> CleanedArxivDocument:
    return CleanedArxivDocument(
        title=title,
        abstract=abstract,
        markdown=f"# {title}\n\n## Abstract\n\n{abstract}\n\n## Recovered Text\n\nBody paragraph.",
        sections=[
            {
                "heading": "Recovered Text",
                "level": 2,
                "paragraphs": ["Body paragraph."],
                "captions": [],
            }
        ],
        appendix_snapshot=[],
        quality={
            "body_chars": 1200,
            "has_abstract": True,
            "section_count": 1,
            "appendix_chars": 0,
            "appendix_sections": 0,
            "bibliography_ratio": 0.0,
            "figure_count": 0,
            "table_count": 0,
            "equation_count": 0,
        },
        figures=[],
        tables=[],
        equations=[],
        capture_fidelity=capture_fidelity,
    )


def _fake_dnl() -> dict:
    sections = {
        "Context": "Context",
        "Related Work": "Related Work",
        "Gap": "Gap",
        "Proposal": "Proposal",
        "Key Results": "Key Results",
        "Discussion": "Discussion",
        "Next Steps": "Next Steps",
    }
    evidence = {key: ["Recovered Text"] for key in sections}
    return {"sections": sections, "evidence": evidence, "confidence": 0.72}


def _runtime(tmpdir: str, mode: str = "local_first", library_id: str = "", api_key: str = "") -> dict:
    return {
        "mode": mode,
        "collection_name": "Paper Distill v2",
        "library_id": library_id,
        "api_key": api_key,
        "local_export_dir": str(Path(tmpdir) / "Paper Distill" / "zotero" / "imports"),
    }


class SettingsToolTest(unittest.TestCase):
    def test_update_learned_preferences_updates_settings_file(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            settings_path = Path(tmpdir) / "settings.json"
            settings_path.write_text(
                json.dumps(
                    {
                        "paper_distill": {
                            "research_profile": {
                                "learned_preferences": {
                                    "accepted_keywords": [],
                                    "rejected_keywords": [],
                                    "preferred_venues": [],
                                    "feedback_count": 0,
                                }
                            }
                        }
                    }
                ),
                encoding="utf-8",
            )

            load_settings.cache_clear()
            with patch.dict(os.environ, {"SETTINGS_PATH": str(settings_path)}, clear=False):
                result = asyncio.run(
                    update_learned_preferences(
                        accepted_keywords=["robotics"],
                        rejected_keywords=["medical"],
                        preferred_venues=["CoRL"],
                    )
                )

            payload = json.loads(settings_path.read_text(encoding="utf-8"))
            prefs = payload["paper_distill"]["research_profile"]["learned_preferences"]
            self.assertTrue(result["updated"])
            self.assertEqual(prefs["accepted_keywords"], ["robotics"])
            self.assertEqual(prefs["rejected_keywords"], ["medical"])
            self.assertEqual(prefs["preferred_venues"], ["CoRL"])
            self.assertEqual(prefs["feedback_count"], 1)
            load_settings.cache_clear()

    def test_analyze_knowledge_graph_accepts_dict_topics_from_settings(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            settings_path = Path(tmpdir) / "settings.json"
            settings_path.write_text(
                json.dumps(
                    {
                        "paper_distill": {
                            "vault_path": tmpdir,
                            "topics": {
                                "vision-language-action": {
                                    "label": "Vision-Language-Action",
                                    "keywords": ["VLA"],
                                },
                                "manipulation": {
                                    "label": "Manipulation",
                                    "keywords": ["manipulation"],
                                },
                            },
                        }
                    }
                ),
                encoding="utf-8",
            )

            ensure_vault_structure(tmpdir)
            load_settings.cache_clear()
            with patch.dict(os.environ, {"SETTINGS_PATH": str(settings_path)}, clear=False):
                result = asyncio.run(analyze_knowledge_graph())

            self.assertNotIn("error", result)
            self.assertEqual(result["paper_count"], 0)
            self.assertEqual(result["concept_count"], 0)
            load_settings.cache_clear()


class WikiWriteToolTest(unittest.TestCase):
    def test_upsert_wiki_article_rejects_invalid_frontmatter_for_papers(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            ensure_vault_structure(tmpdir)
            with patch("server.server.get_vault_path", return_value=tmpdir):
                result = asyncio.run(
                    upsert_wiki_article(
                        citekey="badpaper",
                        section="papers",
                        content="# hi",
                        frontmatter={"bogus": "yes"},
                    )
                )

        self.assertIn("error", result)
        self.assertIn("title", result["error"])


class ProcessInboxRegressionTest(unittest.TestCase):
    def test_process_inbox_preserves_pdf_fallback_capture_method(self) -> None:
        paper = {
            "paper_id": "doi:10.1000/fallback-paper",
            "title": "Fallback Paper",
            "authors": ["Jane Doe"],
            "year": 2026,
            "doi": "10.1000/fallback-paper",
            "arxiv_id": "2601.00010",
            "abstract": "Recovered through PDF fallback.",
            "canonical_pdf_url": "https://arxiv.org/pdf/2601.00010.pdf",
            "canonical_html_url": "https://ar5iv.labs.arxiv.org/html/2601.00010",
            "canonical_item_url": "https://ar5iv.labs.arxiv.org/html/2601.00010",
            "venue": "ICRA 2026",
            "venue_source": "arxiv",
            "capture_method": "pdf_text_recovered",
        }

        with tempfile.TemporaryDirectory() as tmpdir:
            root = ensure_vault_structure(tmpdir)
            write_markdown(
                root / "inbox" / "2026-04-06" / "candidate.md",
                {
                    "paper_id": paper["paper_id"],
                    "status": "approved",
                    "title": paper["title"],
                    "matched_topics": ["manipulation"],
                },
                "# Candidate",
            )

            with patch("server.server.get_vault_path", return_value=tmpdir):
                with patch("server.server._zotero_runtime", return_value=_runtime(tmpdir)):
                    with patch("server.server._capture_settings", return_value=("summary_only", 100)):
                        with patch(
                            "server.server._prepare_ingestion_candidate",
                            new=AsyncMock(
                                return_value=(
                                    dict(paper),
                                    _fake_source_doc(paper["title"], paper["abstract"]),
                                    "",
                                )
                            ),
                        ):
                            with patch("server.server.build_crgp_dnl", return_value=_fake_dnl()):
                                with patch(
                                    "server.server._zotero_add",
                                    new=AsyncMock(
                                        return_value=[
                                            {
                                                "key": "",
                                                "zotero_uri": "",
                                                "zotero_mode": "local_first",
                                                "zotero_status": "local_exported",
                                                "zotero_import_path": "",
                                            }
                                        ]
                                    ),
                                ):
                                    result = asyncio.run(process_inbox())

            self.assertEqual(len(result["processed"]), 1)
            raw_source = query_vault_sync(tmpdir, section="raw_source", detail="full")
            self.assertEqual(raw_source["stats"]["raw_source"], 1)
            self.assertEqual(
                raw_source["sections"]["raw_source"][0]["capture_method"],
                "pdf_text_recovered",
            )
