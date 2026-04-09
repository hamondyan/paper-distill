from __future__ import annotations

import asyncio
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import AsyncMock, patch

from server.config import load_settings
from server.context_assembler import assemble_runtime_context
from server.memory_promotion import promote_memory_event
from server.memory_runtime import append_memory_event
from server.server import analyze_knowledge_graph, discover_papers, query_vault
from server.vault_contract import root_path
from server.vault_ops import ensure_vault_structure, write_markdown


def _settings_payload(vault_path: str) -> dict:
    return {
        "paper_distill": {
            "vault_path": vault_path,
            "topics": {
                "manipulation": {
                    "label": "Manipulation",
                    "keywords": ["manipulation", "robot manipulation"],
                }
            },
            "research_profile": {
                "direction": "Robot manipulation under occlusion and transfer constraints.",
                "whitelist_authors": ["Chelsea Finn"],
                "seed_papers": ["10.48550/arxiv.seed"],
                "learned_preferences": {
                    "accepted_keywords": ["occlusion"],
                    "rejected_keywords": ["medical"],
                    "preferred_venues": ["ICRA"],
                    "feedback_count": 3,
                },
            },
        }
    }


def _append_profile_memory(vault_path: str) -> None:
    result = append_memory_event(
        vault_path,
        event={
            "event_type": "profile_update",
            "view_keys": ["profile"],
            "trust_label": "user-stated",
            "status": "provisional",
            "summary": "The user is focused on manipulation under occlusion and real-world transfer.",
            "content": "Favor ideas and papers that say something concrete about occlusion, failure recovery, or real-robot transfer.",
            "metadata": {
                "direction": "Manipulation with occlusion, transfer, and deployment constraints.",
                "seed_papers": ["10.48550/arxiv.memory-seed"],
            },
        },
    )
    assert result["ok"]
    promoted = promote_memory_event(
        vault_path,
        source_event_id=result["event_id"],
        decision_note="Confirmed as stable profile memory for retrieval and ideation.",
    )
    assert promoted["ok"]
    assert promoted["promoted_event_state"] == "appended"


def _append_taste_memory(vault_path: str) -> None:
    result = append_memory_event(
        vault_path,
        event={
            "event_type": "preference_update",
            "view_keys": ["taste"],
            "trust_label": "user-stated",
            "status": "provisional",
            "summary": "Failure analysis and negative results should outrank benchmark-only gains.",
            "content": "Prefer grounded failure modes, transfer constraints, and diagnostic detail over pure leaderboard deltas.",
            "metadata": {
                "preferred_venues": ["CoRL"],
                "accepted_keywords": ["failure analysis", "negative results"],
            },
        },
    )
    assert result["ok"]
    promoted = promote_memory_event(
        vault_path,
        source_event_id=result["event_id"],
        decision_note="Confirmed as stable taste memory for ranking.",
    )
    assert promoted["ok"]
    assert promoted["promoted_event_state"] == "appended"


def _append_taste_memory_at(
    vault_path: str,
    *,
    now_iso: str,
    summary: str,
    content: str,
    metadata: dict,
) -> None:
    with patch("server.runtime._now_iso", return_value=now_iso):
        result = append_memory_event(
            vault_path,
            event={
                "event_type": "preference_update",
                "view_keys": ["taste"],
                "trust_label": "user-stated",
                "status": "provisional",
                "summary": summary,
                "content": content,
                "metadata": metadata,
            },
        )
    assert result["ok"]
    with patch("server.runtime._now_iso", return_value=now_iso):
        promoted = promote_memory_event(
            vault_path,
            source_event_id=result["event_id"],
            decision_note="Confirmed in context assembler test.",
        )
    assert promoted["ok"]
    assert promoted["promoted_event_state"] == "appended"


class RuntimeContextAssemblerTest(unittest.TestCase):
    def test_assemble_runtime_context_merges_settings_and_memory(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            settings_path = Path(tmpdir) / "settings.json"
            settings_path.write_text(
                json.dumps(_settings_payload(tmpdir)),
                encoding="utf-8",
            )
            ensure_vault_structure(tmpdir)
            _append_profile_memory(tmpdir)
            _append_taste_memory(tmpdir)

            load_settings.cache_clear()
            with patch.dict(
                os.environ,
                {"SETTINGS_PATH": str(settings_path), "VAULT_PATH": tmpdir},
                clear=False,
            ):
                context = assemble_runtime_context(
                    tmpdir,
                    task="query",
                    query_text="What matters for manipulation transfer?",
                    topic_keys=["manipulation"],
                )

            effective = context["effective_preferences"]
            self.assertIn("CoRL", effective["preferred_venues"])
            self.assertIn("ICRA", effective["preferred_venues"])
            self.assertIn("Chelsea Finn", effective["whitelist_authors"])
            self.assertIn("10.48550/arxiv.memory-seed", effective["seed_papers"])
            self.assertIn("failure", " ".join(effective["taste_terms"]))
            self.assertIn("occlusion", " ".join(effective["profile_terms"]))
            self.assertTrue(context["memory"]["available"])
            view_keys = {item["view_key"] for item in context["memory"]["local_evidence"]}
            self.assertEqual(view_keys, {"profile", "taste"})
            load_settings.cache_clear()

    def test_provisional_high_impact_memory_is_visible_but_not_effective_until_promoted(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            settings_path = Path(tmpdir) / "settings.json"
            settings_path.write_text(
                json.dumps(_settings_payload(tmpdir)),
                encoding="utf-8",
            )
            ensure_vault_structure(tmpdir)
            append_result = append_memory_event(
                tmpdir,
                event={
                    "event_type": "preference_update",
                    "view_keys": ["taste"],
                    "trust_label": "user-stated",
                    "status": "provisional",
                    "summary": "Shift toward CoRL failure-analysis papers first.",
                    "content": "Use failure analysis as a leading signal before benchmark wins.",
                    "metadata": {
                        "preferred_venues": ["CoRL"],
                        "accepted_keywords": ["failure analysis"],
                    },
                },
            )
            self.assertTrue(append_result["ok"])

            load_settings.cache_clear()
            with patch.dict(
                os.environ,
                {"SETTINGS_PATH": str(settings_path), "VAULT_PATH": tmpdir},
                clear=False,
            ):
                provisional = assemble_runtime_context(
                    tmpdir,
                    task="query",
                    query_text="What papers should I read next?",
                    topic_keys=["manipulation"],
                )

            self.assertTrue(provisional["memory"]["available"])
            self.assertNotIn("CoRL", provisional["effective_preferences"]["preferred_venues"])
            self.assertNotIn(
                "failure",
                " ".join(provisional["effective_preferences"]["taste_terms"]),
            )

            promoted = promote_memory_event(
                tmpdir,
                source_event_id=append_result["event_id"],
                decision_note="Confirmed for personalization.",
            )
            self.assertTrue(promoted["ok"])
            self.assertEqual(promoted["promoted_event_state"], "appended")

            with patch.dict(
                os.environ,
                {"SETTINGS_PATH": str(settings_path), "VAULT_PATH": tmpdir},
                clear=False,
            ):
                confirmed = assemble_runtime_context(
                    tmpdir,
                    task="query",
                    query_text="What papers should I read next?",
                    topic_keys=["manipulation"],
                )

            self.assertIn("CoRL", confirmed["effective_preferences"]["preferred_venues"])
            self.assertIn(
                "failure",
                " ".join(confirmed["effective_preferences"]["taste_terms"]),
            )
            load_settings.cache_clear()

    def test_query_vault_returns_runtime_context(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            settings_path = Path(tmpdir) / "settings.json"
            settings_path.write_text(
                json.dumps(_settings_payload(tmpdir)),
                encoding="utf-8",
            )
            ensure_vault_structure(tmpdir)
            _append_taste_memory(tmpdir)
            write_markdown(
                root_path(tmpdir, "papers") / "demo-paper.md",
                {
                    "citekey": "demo-paper",
                    "title": "Demo Paper",
                    "topics": ["manipulation"],
                },
                "# Demo Paper",
            )

            load_settings.cache_clear()
            with patch.dict(
                os.environ,
                {"SETTINGS_PATH": str(settings_path), "VAULT_PATH": tmpdir},
                clear=False,
            ):
                result = asyncio.run(query_vault(section="papers", detail="full"))

            self.assertEqual(result["stats"]["papers"], 1)
            self.assertIn("runtime_context", result)
            self.assertTrue(result["runtime_context"]["memory"]["available"])
            self.assertEqual(
                result["runtime_context"]["memory"]["local_evidence"][0]["view_key"],
                "taste",
            )
            load_settings.cache_clear()

    def test_stale_memory_does_not_override_effective_preferences(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            settings_path = Path(tmpdir) / "settings.json"
            settings_path.write_text(
                json.dumps(_settings_payload(tmpdir)),
                encoding="utf-8",
            )
            ensure_vault_structure(tmpdir)
            _append_taste_memory_at(
                tmpdir,
                now_iso="2025-09-01T09:00:00+00:00",
                summary="Older CoRL-heavy taste memory.",
                content="Prefer CoRL and failure analysis first.",
                metadata={
                    "preferred_venues": ["CoRL"],
                    "accepted_keywords": ["failure analysis"],
                },
            )

            load_settings.cache_clear()
            with patch.dict(
                os.environ,
                {"SETTINGS_PATH": str(settings_path), "VAULT_PATH": tmpdir},
                clear=False,
            ):
                context = assemble_runtime_context(
                    tmpdir,
                    task="query",
                    query_text="What should I read next?",
                    topic_keys=["manipulation"],
                )

            self.assertTrue(context["memory"]["available"])
            self.assertNotIn("CoRL", context["effective_preferences"]["preferred_venues"])
            self.assertNotIn(
                "failure",
                " ".join(context["effective_preferences"]["taste_terms"]),
            )
            load_settings.cache_clear()

    def test_idea_discover_returns_runtime_context_and_memory_evidence(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            settings_path = Path(tmpdir) / "settings.json"
            settings_path.write_text(
                json.dumps(_settings_payload(tmpdir)),
                encoding="utf-8",
            )
            ensure_vault_structure(tmpdir)
            _append_profile_memory(tmpdir)
            _append_taste_memory(tmpdir)

            load_settings.cache_clear()
            with patch.dict(
                os.environ,
                {"SETTINGS_PATH": str(settings_path), "VAULT_PATH": tmpdir},
                clear=False,
            ):
                result = asyncio.run(analyze_knowledge_graph(user_topics=["manipulation"]))

            self.assertIn("runtime_context", result)
            self.assertIn("local_memory_evidence", result)
            self.assertGreaterEqual(len(result["local_memory_evidence"]), 2)
            self.assertEqual(
                {item["view_key"] for item in result["local_memory_evidence"]},
                {"profile", "taste"},
            )
            load_settings.cache_clear()

    def test_discovery_uses_runtime_context_for_personalized_ranking(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            settings_path = Path(tmpdir) / "settings.json"
            settings_path.write_text(
                json.dumps(_settings_payload(tmpdir)),
                encoding="utf-8",
            )
            ensure_vault_structure(tmpdir)
            _append_profile_memory(tmpdir)
            _append_taste_memory(tmpdir)

            papers = [
                {
                    "title": "Benchmark Improvements for Robot Manipulation Policies",
                    "abstract": "Robot manipulation paper with small benchmark gains and little analysis.",
                    "authors": ["Jane Doe"],
                    "year": 2026,
                    "venue": "ICRA 2026",
                    "doi": "10.1000/benchmark-only",
                    "citation_count": None,
                    "source": "openalex",
                },
                {
                    "title": "Failure Analysis for Robot Manipulation Under Occlusion",
                    "abstract": "Robot manipulation study focused on negative results, occlusion, and transfer failures.",
                    "authors": ["Jane Doe"],
                    "year": 2026,
                    "venue": "ICRA 2026",
                    "doi": "10.1000/failure-analysis",
                    "citation_count": None,
                    "source": "openalex",
                },
            ]

            def _bind(paper: dict) -> dict:
                suffix = paper["doi"].split("/")[-1]
                return {
                    **paper,
                    "arxiv_id": f"2604.{len(suffix):05d}",
                    "paper_id": f"doi:{paper['doi']}",
                    "canonical_html_url": f"https://ar5iv.labs.arxiv.org/html/{suffix}",
                    "canonical_pdf_url": f"https://arxiv.org/pdf/{suffix}.pdf",
                    "canonical_item_url": f"https://ar5iv.labs.arxiv.org/html/{suffix}",
                    "arxiv_binding_status": "matched",
                }

            load_settings.cache_clear()
            with patch.dict(
                os.environ,
                {"SETTINGS_PATH": str(settings_path), "VAULT_PATH": tmpdir},
                clear=False,
            ):
                with patch("server.server.search_papers", new=AsyncMock(return_value=papers)):
                    with patch("server.server._existing_paper_ids", return_value=set()):
                        with patch("server.server.bind_paper_to_arxiv", new=AsyncMock(side_effect=_bind)):
                            result = asyncio.run(
                                discover_papers(
                                    topic_keys=["manipulation"],
                                    save_to_inbox=False,
                                )
                            )

            self.assertIn("runtime_context", result)
            self.assertEqual(result["papers"][0]["doi"], "10.1000/failure-analysis")
            self.assertGreater(
                result["papers"][0]["_score_breakdown"]["taste_alignment"],
                result["papers"][1]["_score_breakdown"]["taste_alignment"],
            )
            self.assertGreater(
                result["papers"][0]["_score_breakdown"]["profile_alignment"],
                result["papers"][1]["_score_breakdown"]["profile_alignment"],
            )
            load_settings.cache_clear()
