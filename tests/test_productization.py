from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from server.compile_ir import commit_compile_result
from server.concept_registry import register_concept
from server.database import close_db, get_db
from server.vault_ops import (
    append_knowledge_log,
    build_query_asset_body,
    build_query_asset_frontmatter,
    ensure_vault_structure,
    refresh_global_navigation,
    save_query_asset,
    write_markdown,
)


class QueryAssetProtocolTest(unittest.TestCase):
    def test_build_query_asset_frontmatter_uses_unified_protocol(self) -> None:
        frontmatter = build_query_asset_frontmatter(
            note_type="comparison-note",
            title="How VLA Architectures Compare",
            question="How do VLA architectures compare?",
            source_pages=["Paper Distill/wiki/papers/brohan2023rt2.md"],
            papers_referenced=["brohan2023rt2"],
            concepts_referenced=["vision-language-action"],
            topics_referenced=["manipulation"],
            derived_actions=["compile more VLA notes"],
            promotion_targets=[{"page_type": "topic", "page_id": "manipulation"}],
        )

        self.assertEqual(frontmatter["type"], "comparison-note")
        self.assertEqual(frontmatter["status"], "saved")
        self.assertEqual(frontmatter["question"], "How do VLA architectures compare?")
        self.assertEqual(frontmatter["papers_referenced"], ["brohan2023rt2"])
        self.assertEqual(frontmatter["concepts_referenced"], ["vision-language-action"])
        self.assertEqual(frontmatter["topics_referenced"], ["manipulation"])
        self.assertEqual(frontmatter["promotion_targets"][0]["page_type"], "topic")
        self.assertEqual(frontmatter["refresh_state"], "fresh")
        self.assertEqual(frontmatter["stale_dependencies"], [])

    def test_build_query_asset_body_renders_backlinks_and_follow_ups(self) -> None:
        body = build_query_asset_body(
            {
                "title": "How VLA Architectures Compare",
                "question": "How do VLA architectures compare?",
                "summary": "RT-2 and OpenVLA diverge in action tokenization and openness.",
                "answer": "OpenVLA is easier to adapt locally, while RT-2 emphasizes transfer from web-scale pretraining.",
                "source_pages": ["[[papers/brohan2023rt2]]", "[[concepts/vision-language-action]]"],
                "promotion_targets": [{"page_type": "topic", "page_id": "manipulation"}],
                "derived_actions": ["Promote into the manipulation topic page."],
            }
        )

        self.assertIn("How VLA Architectures Compare", body)
        self.assertIn("[[papers/brohan2023rt2]]", body)
        self.assertIn("Promote into the manipulation topic page.", body)

    def test_save_query_asset_tracks_compile_dependencies(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            try:
                ensure_vault_structure(tmpdir)
                register_concept(tmpdir, "Manipulation", concept_type="topic")
                commit_compile_result(
                    tmpdir,
                    "brohan2023rt2",
                    "paper",
                    "Paper body.",
                    {"citekey": "brohan2023rt2", "title": "RT-2", "compile_version": 1},
                )

                result = save_query_asset(
                    tmpdir,
                    asset_id="vla-comparison",
                    note_type="comparison-note",
                    title="How VLA Architectures Compare",
                    question="How do VLA architectures compare?",
                    summary="Saved comparison note.",
                    answer="Answer body.",
                    source_pages=["[[papers/brohan2023rt2]]"],
                    papers_referenced=["brohan2023rt2"],
                    topics_referenced=["manipulation"],
                )

                self.assertTrue(result["written"])
                self.assertIn(
                    "Paper Distill/insights/queries/vla-comparison.md",
                    result["knowledge_impact"]["queries_saved"],
                )

                rows = get_db(tmpdir).execute(
                    """
                    SELECT dep_type, dep_id
                    FROM compile_deps
                    WHERE page_id = 'vla-comparison' AND page_type = 'query'
                    ORDER BY dep_type, dep_id
                    """
                ).fetchall()
                self.assertEqual(
                    [(row["dep_type"], row["dep_id"]) for row in rows],
                    [("paper", "brohan2023rt2"), ("topic", "manipulation")],
                )
            finally:
                close_db(tmpdir)


class NavigationAndLogTest(unittest.TestCase):
    def test_append_knowledge_log_records_structured_event(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = ensure_vault_structure(tmpdir)

            append_knowledge_log(
                tmpdir,
                event_type="query",
                title="Compared VLA architectures",
                summary="Saved a comparison note and linked it back to the wiki.",
                impact={
                    "created_pages": ["Paper Distill/insights/queries/vla-comparison.md"],
                    "updated_pages": [],
                    "linked_pages": ["Paper Distill/wiki/topics/manipulation.md"],
                    "concepts_canonicalized": [],
                    "topics_refreshed": [],
                    "queries_saved": ["Paper Distill/insights/queries/vla-comparison.md"],
                    "maintenance_tasks_created": [],
                    "conflicts_or_skips": [],
                },
            )

            log_text = (root / "log.md").read_text(encoding="utf-8")
            self.assertIn("## [", log_text)
            self.assertIn("query | Compared VLA architectures", log_text)
            self.assertIn("Saved a comparison note", log_text)

    def test_refresh_global_navigation_highlights_recent_query_assets(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = ensure_vault_structure(tmpdir)
            queries_dir = root / "insights" / "queries"
            write_markdown(
                queries_dir / "vla-comparison.md",
                build_query_asset_frontmatter(
                    note_type="comparison-note",
                    title="How VLA Architectures Compare",
                    question="How do VLA architectures compare?",
                    papers_referenced=["brohan2023rt2"],
                    concepts_referenced=["vision-language-action"],
                    topics_referenced=["manipulation"],
                    source_pages=["Paper Distill/wiki/papers/brohan2023rt2.md"],
                    promotion_targets=[{"page_type": "topic", "page_id": "manipulation"}],
                ),
                build_query_asset_body(
                    {
                        "title": "How VLA Architectures Compare",
                        "question": "How do VLA architectures compare?",
                        "summary": "A saved comparison note.",
                        "answer": "Answer body.",
                        "source_pages": ["[[papers/brohan2023rt2]]"],
                        "promotion_targets": [{"page_type": "topic", "page_id": "manipulation"}],
                        "derived_actions": [],
                    }
                ),
            )

            refresh_global_navigation(tmpdir)

            index_text = (root / "index.md").read_text(encoding="utf-8")
            self.assertIn("Recent Query Assets", index_text)
            self.assertIn("How VLA Architectures Compare", index_text)
