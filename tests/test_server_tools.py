from __future__ import annotations

import asyncio
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import AsyncMock, patch

import yaml

from server.arxiv_capture import CleanedArxivDocument
from server.config import load_settings
from server.idea_verification import verify_idea
from server.memory_runtime import append_memory_event, read_memory_views
from server.server import (
    analyze_knowledge_graph,
    commit_compile_result as knowledge_compile_publish,
    get_compile_state as knowledge_compile_status,
    mcp,
    process_inbox,
    query_tension_signals,
    query_vault,
    resolve_compile_ir,
    source_ingest,
    update_learned_preferences,
    upsert_wiki_article,
    write_compile_ir,
)
from server.vault_contract import root_path
from server.vault_ops import ensure_vault_structure, write_markdown
from server.vault_query import query_vault_sync

_FIXTURE_ROOT = Path(__file__).with_name("fixtures") / "wave1_replay"


def _load_replay_json(name: str) -> dict:
    return json.loads((_FIXTURE_ROOT / name).read_text(encoding="utf-8"))


def _load_replay_text(name: str) -> str:
    return (_FIXTURE_ROOT / name).read_text(encoding="utf-8")


def _replay_paper() -> dict:
    return dict(_load_replay_json("paper.json"))


def _replay_source_doc() -> CleanedArxivDocument:
    return CleanedArxivDocument(**_load_replay_json("source_doc.json"))


def _replay_memory_event() -> dict:
    return dict(_load_replay_json("memory_event.json"))


def _replay_idea() -> dict:
    return dict(_load_replay_json("idea.json"))


def _replay_verification() -> dict:
    return dict(_load_replay_json("verification_verified.json"))


def _read_frontmatter(path: Path) -> dict:
    content = path.read_text(encoding="utf-8")
    _, remainder = content.split("---\n", 1)
    fm_text, _ = remainder.split("\n---\n", 1)
    return yaml.safe_load(fm_text) or {}


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
            source_evidence = query_vault_sync(tmpdir, section="source_evidence", detail="full")
            self.assertEqual(source_evidence["stats"]["source_evidence"], 1)
            self.assertEqual(
                source_evidence["sections"]["source_evidence"][0]["capture_method"],
                "pdf_text_recovered",
            )
            self.assertIn("knowledge_impact", result)
            # Only source_evidence is created during ingest; wiki page created by /compile
            self.assertEqual(len(result["knowledge_impact"]["created_pages"]), 1)
            self.assertEqual(len(result["knowledge_impact"]["updated_pages"]), 1)
            log_text = (Path(tmpdir) / "Paper Distill" / "log.md").read_text(encoding="utf-8")
            self.assertIn("source-ingest", log_text)
            self.assertIn("Fallback Paper", log_text)

    def test_source_ingest_approved_inbox_uses_sources_contract(self) -> None:
        paper = _replay_paper()

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
                                    _replay_source_doc(),
                                    "",
                                )
                            ),
                        ):
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
                                result = asyncio.run(
                                    source_ingest(mode="approved_inbox", limit=1)
                                )

            self.assertEqual(len(result["processed"]), 1)
            processed = result["processed"][0]
            self.assertIn("/Paper Distill/sources/evidence/", processed["source_evidence_abs_path"])
            self.assertIn("/Paper Distill/wiki/papers/", processed["wiki_paper_abs_path"])


class ToolSurfaceContractTest(unittest.TestCase):
    def test_consolidated_mcp_surface_names(self) -> None:
        tools = asyncio.run(mcp.list_tools())
        names = {tool.name for tool in tools}

        expected = {
            "status",
            "kb_search",
            "kb_get",
            "discover_papers",
            "ingest_and_read",
            "check_concept_alias",
            "upsert_wiki_page",
            "merge_concept",
            "kb_update_index",
            "kb_reembed_force",
            "lint_vault",
        }
        self.assertEqual(names, expected)

        # Old tool names should NOT be present
        self.assertNotIn("update-preferences", names)
        self.assertNotIn("search-papers", names)
        self.assertNotIn("read-paper", names)
        self.assertNotIn("compile", names)
        self.assertNotIn("write-wiki", names)
        self.assertNotIn("concept", names)
        self.assertNotIn("maintain", names)
        self.assertNotIn("idea-analyze", names)
        self.assertNotIn("vault-health", names)
        self.assertNotIn("query-library", names)
        self.assertNotIn("discover", names)
        self.assertNotIn("ingest", names)
        self.assertNotIn("upsert-wiki-page", names)
        self.assertNotIn("check-concept-alias", names)
        self.assertNotIn("source-discover", names)
        self.assertNotIn("source-ingest", names)
        self.assertNotIn("knowledge-compile-publish", names)
        self.assertNotIn("paper-distill-extract", names)
        self.assertNotIn("idea-discover", names)
        self.assertNotIn("score_papers", names)
        self.assertNotIn("bootstrap-library", names)
        self.assertNotIn("export_db_state", names)
        self.assertNotIn("backfill_registry", names)
        self.assertNotIn("zotero_add", names)
        self.assertNotIn("zotero_search", names)

    def test_knowledge_compile_publish_surface_reports_status_after_publish(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            ensure_vault_structure(tmpdir)

            with patch("server.server.get_vault_path", return_value=tmpdir):
                result = asyncio.run(
                    knowledge_compile_publish(
                        page_id="adapter2026",
                        page_type="paper",
                        content=_load_replay_text("compiled_paper.md"),
                        frontmatter={
                            "citekey": "adapter2026",
                            "title": "Adapter Contract Paper",
                            "compile_version": 1,
                        },
                    )
                )
                status = asyncio.run(
                    knowledge_compile_status(page_id="adapter2026", page_type="paper")
                )

        self.assertTrue(result["written"])
        self.assertEqual(status["page_id"], "adapter2026")
        self.assertEqual(status["page_type"], "paper")
        self.assertEqual(status["compile_version"], 1)
        self.assertEqual(status["schema_version"], "2024-06")

    def test_source_ingest_direct_mode_exposes_only_final_result_keys(self) -> None:
        with patch(
            "server.server.add_paper",
            new=AsyncMock(
                return_value={
                    "added": True,
                    "source_evidence_abs_path": "/tmp/Paper Distill/sources/evidence/2026-04-09/example.md",
                    "wiki_paper_abs_path": "/tmp/Paper Distill/wiki/papers/example.md",
                    "source_evidence_path": "Paper Distill/sources/evidence/2026-04-09/example.md",
                    "source_assets_path": "Paper Distill/sources/evidence/2026-04-09/example.assets.json",
                    "wiki_paper_path": "Paper Distill/wiki/papers/example.md",
                }
            ),
        ):
            result = asyncio.run(
                source_ingest(
                    mode="direct_identifier",
                    identifier="10.1000/example",
                )
            )

        self.assertTrue(result["added"])
        self.assertEqual(
            result["source_evidence_abs_path"],
            "/tmp/Paper Distill/sources/evidence/2026-04-09/example.md",
        )
        self.assertEqual(
            result["wiki_paper_abs_path"],
            "/tmp/Paper Distill/wiki/papers/example.md",
        )
        self.assertEqual(
            result["source_evidence_path"],
            "Paper Distill/sources/evidence/2026-04-09/example.md",
        )
        self.assertEqual(
            result["source_assets_path"],
            "Paper Distill/sources/evidence/2026-04-09/example.assets.json",
        )
        self.assertEqual(
            result["wiki_paper_path"],
            "Paper Distill/wiki/papers/example.md",
        )

    def test_source_ingest_requires_identifier_in_direct_mode(self) -> None:
        result = asyncio.run(source_ingest(mode="direct_identifier"))
        self.assertIn("error", result)
        self.assertIn("identifier", result["error"])


class Wave1ReplaySmokeTest(unittest.TestCase):
    def test_wave1_smoke_flow_replays_full_core_path_without_network(self) -> None:
        paper = _replay_paper()
        source_doc = _replay_source_doc()
        ir = _load_replay_json("compile_ir.json")
        compiled_body = _load_replay_text("compiled_paper.md")
        memory_event = _replay_memory_event()
        idea = _replay_idea()
        verification = _replay_verification()

        with tempfile.TemporaryDirectory() as tmpdir:
            ensure_vault_structure(tmpdir)
            write_markdown(
                root_path(tmpdir, "memory") / "taste.md",
                {"view_key": "taste", "compiled_at": "2026-04-08T22:00:00"},
                "# Taste\n\nCompiled memory says grounded robotics evidence matters more than benchmark-only gains.",
            )

            with patch("server.server.get_vault_path", return_value=tmpdir):
                with patch("server.server._zotero_runtime", return_value=_runtime(tmpdir)):
                    with patch("server.server._capture_settings", return_value=("summary_only", 100)):
                        with patch(
                            "server.server._resolve_explicit_paper",
                            new=AsyncMock(return_value=dict(paper)),
                        ):
                            with patch(
                                "server.server._prepare_direct_add_candidate",
                                new=AsyncMock(
                                    return_value=(
                                        dict(paper),
                                        source_doc,
                                        source_doc.capture_method,
                                        "",
                                    )
                                ),
                            ):
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
                                    ingest = asyncio.run(
                                        source_ingest(
                                            mode="direct_identifier",
                                            identifier=paper["doi"],
                                            topic_keys=["manipulation"],
                                        )
                                    )
                                    extract = asyncio.run(
                                        write_compile_ir(ir["citekey"], ir)
                                    )
                                    resolve = asyncio.run(
                                        resolve_compile_ir([ir["citekey"]])
                                    )

                                    deps = [
                                        {
                                            "dep_type": ir["candidate_concepts"][index].get("type", "concept"),
                                            "dep_id": resolution["canonical_id"],
                                            "dep_version": 1,
                                        }
                                        for index, resolution in enumerate(resolve[0]["resolutions"])
                                    ]
                                    publish = asyncio.run(
                                        knowledge_compile_publish(
                                            page_id=ir["citekey"],
                                            page_type="paper",
                                            content=compiled_body,
                                            frontmatter={
                                                "citekey": ir["citekey"],
                                                "title": paper["title"],
                                                "compile_version": 1,
                                                "topics": ["manipulation"],
                                            },
                                            ir_path=f"Paper Distill/.state/ir/{ir['citekey']}_resolved.json",
                                            deps=deps,
                                        )
                                    )
                                    status = asyncio.run(
                                        knowledge_compile_status(
                                            page_id=ir["citekey"],
                                            page_type="paper",
                                        )
                                    )
                                    papers = asyncio.run(
                                        query_vault(section="papers", detail="full")
                                    )
                                    source_evidence = asyncio.run(
                                        query_vault(section="source_evidence", detail="full")
                                    )
                                    signals = asyncio.run(
                                        query_tension_signals(min_occurrence=1)
                                    )

            idea["local_evidence"]["wiki"][0]["ref"] = f"Paper Distill/wiki/papers/{ir['citekey']}.md"
            idea["local_evidence"]["sources"][0]["ref"] = ingest["source_evidence_path"]
            memory_result = append_memory_event(tmpdir, event=memory_event)
            memory_state = read_memory_views(tmpdir, view_keys=["taste"])
            idea["local_evidence"]["memory"][0]["summary"] = memory_state["views"]["taste"]["overlay_events"][0]["summary"]
            idea_result = verify_idea(
                tmpdir,
                idea=idea,
                verification=verification,
            )

            self.assertTrue(ingest["added"])
            self.assertTrue(Path(ingest["source_evidence_abs_path"]).exists())
            self.assertTrue(Path(ingest["wiki_paper_abs_path"]).exists())
            self.assertTrue(Path(root_path(tmpdir, "papers") / f"{ir['citekey']}.md").exists())

            self.assertTrue(extract["valid"])
            self.assertEqual(resolve[0]["resolved_count"], 1)
            self.assertTrue(publish["written"])
            self.assertEqual(status["page_id"], ir["citekey"])
            self.assertEqual(status["compile_version"], 1)

            self.assertEqual(papers["stats"]["papers"], 1)
            self.assertEqual(papers["sections"]["papers"][0]["citekey"], ir["citekey"])
            self.assertEqual(source_evidence["stats"]["source_evidence"], 1)
            self.assertEqual(signals["papers_scanned"], 1)
            self.assertEqual(signals["claimed_novelties"][0]["paper"], ir["citekey"])

            self.assertTrue(memory_result["ok"])
            self.assertTrue(memory_result["appended"])
            self.assertTrue(memory_state["overlay_applied"])
            self.assertEqual(memory_state["uncompiled_event_count"], 1)
            self.assertEqual(
                memory_state["views"]["taste"]["overlay_events"][0]["event_id"],
                memory_result["event_id"],
            )
            self.assertEqual(
                memory_state["views"]["taste"]["overlay_events"][0]["summary"],
                memory_event["summary"],
            )

            self.assertTrue(idea_result["ok"])
            self.assertEqual(idea_result["idea_state"], "active")
            self.assertEqual(idea_result["verification_state"], "verified")
            self.assertEqual(idea_result["decision_reason"], "")
            self.assertTrue(Path(idea_result["idea_path"]).exists())
            self.assertEqual(
                list((Path(tmpdir) / "Paper Distill" / "insights" / "verification").rglob("*.json")),
                [],
            )

            memo_frontmatter = _read_frontmatter(Path(idea_result["idea_path"]))
            self.assertEqual(memo_frontmatter["idea_state"], "active")
            self.assertEqual(memo_frontmatter["verification_state"], "verified")
            self.assertEqual(memo_frontmatter["decision_reason"], "")
