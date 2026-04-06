from __future__ import annotations

import asyncio
import tempfile
import unittest
from pathlib import Path
from unittest.mock import AsyncMock, patch

from server.arxiv_capture import CleanedArxivDocument
from server.server import _capture_options, _prepare_direct_add_candidate, _source_doc_sidecar_payload, add_paper
from server.vault_ops import ensure_vault_structure, write_markdown
from server.vault_query import query_vault_sync


def _fake_source_doc(
    title: str,
    abstract: str,
    *,
    capture_source: str = "ar5iv_html",
    capture_method: str = "ar5iv_html_cleaned",
) -> CleanedArxivDocument:
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
            "figure_count": 1,
            "table_count": 1,
            "equation_count": 1,
        },
        figures=[
            {
                "label": "Figure 1",
                "caption": "Figure 1: Architecture overview.",
                "section": "Recovered Text",
                "image_url": "",
                "alt_text": "",
            }
        ],
        tables=[
            {
                "label": "Table 1",
                "caption": "Table 1: Main results.",
                "section": "Recovered Text",
                "summary": "Table 1: Main results.",
                "markdown": "| A | B |\n| --- | --- |\n| 1 | 2 |",
                "row_count": 2,
                "column_count": 2,
            }
        ],
        equations=[
            {
                "label": "Equation E1",
                "section": "Recovered Text",
                "text": "a_t = \\pi(o_t, g_t)",
            }
        ],
        capture_fidelity="high",
        capture_source=capture_source,
        capture_method=capture_method,
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


class PaperAddTest(unittest.TestCase):
    def test_capture_options_include_reference_and_citation_controls(self) -> None:
        with patch(
            "server.server.get_paper_distill_settings",
            return_value={
                "capture": {
                    "remove_refs": False,
                    "remove_inline_citations": True,
                    "remove_internal_links": False,
                }
            },
        ):
            options = _capture_options()

        self.assertFalse(options["remove_refs"])
        self.assertTrue(options["remove_inline_citations"])
        self.assertFalse(options["remove_internal_links"])

    def test_add_paper_requires_identifier(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            with patch("server.server.get_vault_path", return_value=tmpdir):
                with patch("server.server._zotero_runtime", return_value=_runtime(tmpdir)):
                    result = asyncio.run(add_paper("   "))

        self.assertEqual(result["error"], "identifier is required")

    def test_add_paper_requires_web_api_credentials(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            with patch("server.server.get_vault_path", return_value=tmpdir):
                with patch(
                    "server.server._zotero_runtime",
                    return_value=_runtime(tmpdir, mode="web_api"),
                ):
                    result = asyncio.run(add_paper("10.1000/test-add"))

        self.assertIn("ZOTERO_LIBRARY_ID", result["error"])

    def test_add_paper_returns_error_when_identifier_cannot_be_resolved(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            prepare_mock = AsyncMock()
            with patch("server.server.get_vault_path", return_value=tmpdir):
                with patch("server.server._zotero_runtime", return_value=_runtime(tmpdir)):
                    with patch("server.server._resolve_explicit_paper", new=AsyncMock(return_value={})):
                        with patch("server.server._prepare_direct_add_candidate", new=prepare_mock):
                            result = asyncio.run(add_paper("https://example.com/unknown"))

        self.assertEqual(result["error"], "Could not resolve metadata from the provided identifier")
        prepare_mock.assert_not_called()

    def test_add_paper_returns_capture_error_without_writing(self) -> None:
        paper = {
            "paper_id": "doi:10.1000/capture-fail",
            "title": "Capture Failure",
            "authors": ["Jane Doe"],
            "year": 2026,
            "doi": "10.1000/capture-fail",
        }

        with tempfile.TemporaryDirectory() as tmpdir:
            with patch("server.server.get_vault_path", return_value=tmpdir):
                with patch("server.server._zotero_runtime", return_value=_runtime(tmpdir)):
                    with patch("server.server._capture_settings", return_value=("summary_only", 100)):
                        with patch("server.server._resolve_explicit_paper", new=AsyncMock(return_value=dict(paper))):
                            with patch(
                                "server.server._prepare_direct_add_candidate",
                                new=AsyncMock(return_value=(dict(paper), None, "", "capture failed hard")),
                            ):
                                result = asyncio.run(add_paper("10.1000/capture-fail"))

            self.assertFalse(result["added"])
            self.assertEqual(result["error"], "capture failed hard")
            self.assertEqual(query_vault_sync(tmpdir, section="raw_source")["stats"]["raw_source"], 0)
            self.assertEqual(query_vault_sync(tmpdir, section="raw_notes")["stats"]["raw_notes"], 0)

    def test_add_paper_writes_raw_layers_and_local_export(self) -> None:
        paper = {
            "paper_id": "doi:10.1000/test-add",
            "title": "A Direct Add Paper",
            "authors": ["Jane Doe"],
            "year": 2026,
            "doi": "10.1000/test-add",
            "arxiv_id": "2601.00001",
            "abstract": "An embodied AI paper.",
            "canonical_pdf_url": "https://arxiv.org/pdf/2601.00001.pdf",
            "canonical_html_url": "https://ar5iv.labs.arxiv.org/html/2601.00001",
            "canonical_item_url": "https://ar5iv.labs.arxiv.org/html/2601.00001",
            "venue": "ICRA 2026",
            "venue_source": "arxiv",
        }

        with tempfile.TemporaryDirectory() as tmpdir:
            with patch("server.server.get_vault_path", return_value=tmpdir):
                with patch(
                    "server.server._zotero_runtime",
                    return_value=_runtime(tmpdir),
                ):
                    with patch("server.server._capture_settings", return_value=("summary_only", 100)):
                        with patch("server.server._resolve_explicit_paper", new=AsyncMock(return_value=dict(paper))):
                            with patch(
                                "server.server._prepare_direct_add_candidate",
                                new=AsyncMock(return_value=(dict(paper), _fake_source_doc(paper["title"], paper["abstract"]), "ar5iv_html_cleaned", "")),
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
                                                    "zotero_import_path": str(
                                                        Path(tmpdir)
                                                        / "Paper Distill"
                                                        / "zotero"
                                                        / "imports"
                                                        / "doe2026-direct.csl.json"
                                                    ),
                                                }
                                            ]
                                        ),
                                    ):
                                        result = asyncio.run(add_paper("10.1000/test-add"))

            self.assertTrue(result["added"])
            self.assertEqual(result["zotero_status"], "local_exported")
            self.assertTrue(Path(result["raw_source_path"]).exists())
            self.assertTrue(Path(result["raw_note_path"]).exists())
            self.assertTrue((Path(tmpdir) / result["source_structured_path"]).exists())

            raw_notes = query_vault_sync(tmpdir, section="raw_notes")
            self.assertEqual(raw_notes["stats"]["raw_notes"], 1)
            self.assertEqual(raw_notes["sections"]["raw_notes"][0]["paper_id"], paper["paper_id"])
            self.assertEqual(raw_notes["sections"]["raw_notes"][0]["zotero_status"], "local_exported")
            self.assertEqual(raw_notes["sections"]["raw_notes"][0]["capture_fidelity"], "high")

    def test_add_paper_returns_existing_record_without_rewriting(self) -> None:
        paper = {
            "paper_id": "doi:10.1000/existing",
            "title": "Already Added",
            "authors": ["Jane Doe"],
            "year": 2026,
            "doi": "10.1000/existing",
            "abstract": "Existing note.",
        }

        with tempfile.TemporaryDirectory() as tmpdir:
            root = ensure_vault_structure(tmpdir)
            note_path = root / "raw" / "notes" / "2026-04-05" / "doe2026-existing.md"
            write_markdown(
                note_path,
                {
                    "paper_id": paper["paper_id"],
                    "citekey": "doe2026-existing",
                    "title": paper["title"],
                    "doi": paper["doi"],
                    "compiled": False,
                    "source_raw_path": "Paper Distill/raw/source/2026-04-05/doe2026-existing.md",
                },
                "# Existing",
            )

            prepare_mock = AsyncMock()
            zotero_mock = AsyncMock()
            with patch("server.server.get_vault_path", return_value=tmpdir):
                with patch(
                    "server.server._zotero_runtime",
                    return_value=_runtime(tmpdir),
                ):
                    with patch("server.server._resolve_explicit_paper", new=AsyncMock(return_value=paper)):
                        with patch("server.server._prepare_direct_add_candidate", new=prepare_mock):
                            with patch("server.server._zotero_add", new=zotero_mock):
                                result = asyncio.run(add_paper("10.1000/existing"))

            self.assertFalse(result["added"])
            self.assertTrue(result["existing"])
            self.assertTrue(result["raw_note_path"].endswith("doe2026-existing.md"))
            prepare_mock.assert_not_called()
            zotero_mock.assert_not_called()

    def test_add_paper_keeps_raw_layers_when_zotero_fails(self) -> None:
        paper = {
            "paper_id": "hash:abc123",
            "title": "PDF Only Paper",
            "authors": [],
            "year": 2026,
            "doi": "",
            "abstract": "Recovered from PDF.",
            "canonical_pdf_url": "https://example.com/paper.pdf",
            "canonical_item_url": "https://example.com/paper.pdf",
            "venue": "",
            "venue_source": "pdf",
        }

        with tempfile.TemporaryDirectory() as tmpdir:
            with patch("server.server.get_vault_path", return_value=tmpdir):
                with patch(
                    "server.server._zotero_runtime",
                    return_value=_runtime(tmpdir),
                ):
                    with patch("server.server._capture_settings", return_value=("summary_only", 100)):
                        with patch("server.server._resolve_explicit_paper", new=AsyncMock(return_value=dict(paper))):
                            with patch(
                                "server.server._prepare_direct_add_candidate",
                                new=AsyncMock(return_value=(dict(paper), _fake_source_doc(paper["title"], paper["abstract"]), "pdf_text_recovered", "")),
                            ):
                                with patch("server.server.build_crgp_dnl", return_value=_fake_dnl()):
                                    with patch(
                                        "server.server._zotero_add",
                                        new=AsyncMock(return_value=[{"error": "Local Zotero export failed"}]),
                                    ):
                                        result = asyncio.run(add_paper("https://example.com/paper.pdf"))

            self.assertTrue(result["added"])
            self.assertEqual(result["zotero_status"], "error")
            self.assertIn("Local Zotero export failed", result["warning"])
            self.assertTrue(Path(result["raw_source_path"]).exists())
            self.assertTrue(Path(result["raw_note_path"]).exists())

            raw_source = query_vault_sync(tmpdir, section="raw_source")
            self.assertEqual(raw_source["stats"]["raw_source"], 1)
            self.assertEqual(raw_source["sections"]["raw_source"][0]["capture_method"], "pdf_text_recovered")

    def test_add_paper_detects_existing_paper_by_pdf_url(self) -> None:
        paper = {
            "paper_id": "hash:pdf-only",
            "title": "URL Dedup Paper",
            "authors": [],
            "year": None,
            "doi": "",
            "arxiv_id": "",
            "canonical_pdf_url": "https://example.com/dedup.pdf",
            "canonical_item_url": "https://example.com/dedup.pdf",
        }

        with tempfile.TemporaryDirectory() as tmpdir:
            root = ensure_vault_structure(tmpdir)
            note_path = root / "raw" / "notes" / "2026-04-05" / "url-dedup.md"
            write_markdown(
                note_path,
                {
                    "paper_id": "hash:existing-url-note",
                    "title": "Existing URL Paper",
                    "compiled": False,
                    "canonical_pdf_url": "https://example.com/dedup.pdf",
                    "source_raw_path": "Paper Distill/raw/source/2026-04-05/url-dedup-source.md",
                },
                "# Existing URL Paper",
            )

            prepare_mock = AsyncMock()
            zotero_mock = AsyncMock()
            with patch("server.server.get_vault_path", return_value=tmpdir):
                with patch("server.server._zotero_runtime", return_value=_runtime(tmpdir)):
                    with patch("server.server._resolve_explicit_paper", new=AsyncMock(return_value=paper)):
                        with patch("server.server._prepare_direct_add_candidate", new=prepare_mock):
                            with patch("server.server._zotero_add", new=zotero_mock):
                                result = asyncio.run(add_paper("https://example.com/dedup.pdf"))

        self.assertFalse(result["added"])
        self.assertTrue(result["existing"])
        self.assertTrue(result["raw_note_path"].endswith("url-dedup.md"))
        prepare_mock.assert_not_called()
        zotero_mock.assert_not_called()

    def test_add_paper_passes_topic_keys_and_collection_override(self) -> None:
        paper = {
            "paper_id": "doi:10.1000/topic-paper",
            "title": "Manipulation Paper",
            "authors": ["Jane Doe"],
            "year": 2026,
            "doi": "10.1000/topic-paper",
            "abstract": "A manipulation paper.",
            "canonical_pdf_url": "https://arxiv.org/pdf/2601.00002.pdf",
            "canonical_html_url": "https://ar5iv.labs.arxiv.org/html/2601.00002",
            "canonical_item_url": "https://ar5iv.labs.arxiv.org/html/2601.00002",
            "venue": "ICRA 2026",
            "venue_source": "arxiv",
        }
        prepared_paper = {
            **paper,
            "topic_tags": ["manipulation"],
            "collection_name": "My Custom Collection",
        }

        captured: dict = {}

        async def fake_zotero_add(papers: list[dict], *_args, **_kwargs) -> list[dict]:
            captured["paper"] = dict(papers[0])
            return [
                {
                    "key": "",
                    "zotero_uri": "",
                    "zotero_mode": "local_first",
                    "zotero_status": "local_exported",
                    "zotero_import_path": "",
                }
            ]

        with tempfile.TemporaryDirectory() as tmpdir:
            with patch("server.server.get_vault_path", return_value=tmpdir):
                with patch("server.server._zotero_runtime", return_value=_runtime(tmpdir)):
                    with patch("server.server._capture_settings", return_value=("summary_only", 100)):
                        with patch("server.server._resolve_explicit_paper", new=AsyncMock(return_value=dict(paper))):
                            with patch(
                                "server.server._prepare_direct_add_candidate",
                                new=AsyncMock(return_value=(prepared_paper, _fake_source_doc(paper["title"], paper["abstract"]), "ar5iv_html_cleaned", "")),
                            ):
                                with patch("server.server.build_crgp_dnl", return_value=_fake_dnl()):
                                    with patch("server.server._zotero_add", new=fake_zotero_add):
                                        result = asyncio.run(
                                            add_paper(
                                                "10.1000/topic-paper",
                                                topic_keys=["manipulation"],
                                                collection_name="My Custom Collection",
                                            )
                                        )

        self.assertTrue(result["added"])
        self.assertEqual(result["matched_topics"], ["manipulation"])
        self.assertEqual(captured["paper"]["topic_tags"], ["manipulation"])
        self.assertEqual(captured["paper"]["collection_name"], "My Custom Collection")

    def test_prepare_direct_add_candidate_passes_capture_policy_options(self) -> None:
        paper = {
            "paper_id": "arxiv:2601.00001",
            "title": "A Direct Add Paper",
            "authors": ["Jane Doe"],
            "year": 2026,
            "arxiv_id": "2601.00001",
            "abstract": "An embodied AI paper.",
            "canonical_pdf_url": "https://arxiv.org/pdf/2601.00001.pdf",
            "canonical_html_url": "https://ar5iv.labs.arxiv.org/html/2601.00001",
            "canonical_item_url": "https://ar5iv.labs.arxiv.org/html/2601.00001",
            "venue": "ICRA 2026",
            "venue_source": "arxiv",
        }
        capture_mock = AsyncMock(return_value=_fake_source_doc(paper["title"], paper["abstract"]))

        with patch("server.server.capture_arxiv_source", new=capture_mock):
            prepared, source_doc, capture_method, error = asyncio.run(
                _prepare_direct_add_candidate(
                    paper,
                    "arxiv:2601.00001",
                    "summary_only",
                    100,
                    capture_options={
                        "remove_refs": False,
                        "remove_inline_citations": True,
                        "remove_internal_links": False,
                    },
                )
            )

        self.assertEqual(error, "")
        self.assertEqual(capture_method, "ar5iv_html_cleaned")
        self.assertIsNotNone(source_doc)
        self.assertEqual(prepared["title"], paper["title"])
        self.assertEqual(capture_mock.await_args.kwargs["remove_refs"], False)
        self.assertEqual(capture_mock.await_args.kwargs["remove_inline_citations"], True)
        self.assertEqual(capture_mock.await_args.kwargs["remove_internal_links"], False)

    def test_prepare_direct_add_candidate_uses_native_capture_method_when_present(self) -> None:
        paper = {
            "paper_id": "arxiv:2601.00001",
            "title": "A Direct Add Paper",
            "authors": ["Jane Doe"],
            "year": 2026,
            "arxiv_id": "2601.00001",
            "abstract": "An embodied AI paper.",
            "canonical_pdf_url": "https://arxiv.org/pdf/2601.00001.pdf",
            "canonical_html_url": "https://ar5iv.labs.arxiv.org/html/2601.00001",
            "canonical_item_url": "https://ar5iv.labs.arxiv.org/html/2601.00001",
            "venue": "ICRA 2026",
            "venue_source": "arxiv",
        }
        capture_mock = AsyncMock(
            return_value=_fake_source_doc(
                paper["title"],
                paper["abstract"],
                capture_source="arxiv_native_html",
                capture_method="arxiv_native_html_cleaned",
            )
        )

        with patch("server.server.capture_arxiv_source", new=capture_mock):
            _prepared, _source_doc, capture_method, error = asyncio.run(
                _prepare_direct_add_candidate(
                    paper,
                    "arxiv:2601.00001",
                    "summary_only",
                    100,
                    capture_options={},
                )
            )

        self.assertEqual(error, "")
        self.assertEqual(capture_method, "arxiv_native_html_cleaned")

    def test_source_doc_sidecar_payload_includes_capture_provenance(self) -> None:
        payload = _source_doc_sidecar_payload(
            _fake_source_doc(
                "A Direct Add Paper",
                "An embodied AI paper.",
                capture_source="arxiv_native_html",
                capture_method="arxiv_native_html_cleaned",
            )
        )

        self.assertEqual(payload["capture_source"], "arxiv_native_html")
        self.assertEqual(payload["capture_method"], "arxiv_native_html_cleaned")
