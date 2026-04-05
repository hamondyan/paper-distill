from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from server.vault_lint import (
    analyze_knowledge_graph_sync,
    lint_vault_sync,
    vault_stats_sync,
)
from server.vault_ops import ensure_vault_structure, write_markdown


def _make_vault(tmpdir: str) -> Path:
    """Bootstrap a minimal vault and return the vault root."""
    ensure_vault_structure(tmpdir)
    return Path(tmpdir) / "Paper Distill"


class LintVaultTest(unittest.TestCase):
    def test_clean_vault_reports_good(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            _make_vault(tmpdir)
            result = lint_vault_sync(tmpdir)
            self.assertEqual(result["overall_health"], "good")
            self.assertEqual(result["broken_backlinks"]["count"], 0)

    def test_broken_backlinks_detected(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = _make_vault(tmpdir)
            write_markdown(
                root / "wiki" / "papers" / "smith2024-foo.md",
                {"citekey": "smith2024-foo", "title": "Foo Paper"},
                "# Foo\n\nSee [[concepts/nonexistent-concept]].",
            )
            result = lint_vault_sync(tmpdir)
            self.assertGreater(result["broken_backlinks"]["count"], 0)
            targets = [b["target"] for b in result["broken_backlinks"]["items"]]
            self.assertIn("concepts/nonexistent-concept", targets)

    def test_missing_frontmatter_detected(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = _make_vault(tmpdir)
            # Write inbox note missing required 'status' field
            note = root / "inbox" / "2026-04-05" / "bad-note.md"
            note.parent.mkdir(parents=True, exist_ok=True)
            note.write_text("---\npaper_id: test\n---\n# Bad\n", encoding="utf-8")

            result = lint_vault_sync(tmpdir)
            self.assertGreater(result["missing_frontmatter"]["count"], 0)
            items = result["missing_frontmatter"]["items"]
            missing_fields = [i["missing_fields"] for i in items]
            self.assertTrue(any("status" in fields for fields in missing_fields))

    def test_uncompiled_papers_detected(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = _make_vault(tmpdir)
            write_markdown(
                root / "raw" / "notes" / "2026-04-05" / "jones2024-bar.md",
                {"paper_id": "arxiv:2401.00001", "compiled": False, "title": "Bar"},
                "# Bar",
            )
            result = lint_vault_sync(tmpdir)
            self.assertEqual(result["uncompiled_papers"]["count"], 1)

    def test_missing_concept_stubs_detected(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = _make_vault(tmpdir)
            # Paper references a concept that doesn't exist
            write_markdown(
                root / "wiki" / "papers" / "doe2024-baz.md",
                {"citekey": "doe2024-baz", "title": "Baz Paper"},
                "# Baz\n\nRelated to [[concepts/missing-thing]].",
            )
            result = lint_vault_sync(tmpdir)
            self.assertGreater(result["missing_concept_stubs"]["count"], 0)
            self.assertIn("concepts/missing-thing", result["missing_concept_stubs"]["items"])

    def test_orphaned_articles_detected(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = _make_vault(tmpdir)
            # Create a concept that nobody links to
            write_markdown(
                root / "wiki" / "concepts" / "lonely-concept.md",
                {"concept": "Lonely Concept"},
                "# Lonely Concept\n\nNobody references me.",
            )
            result = lint_vault_sync(tmpdir)
            self.assertGreater(result["orphaned_articles"]["count"], 0)
            self.assertTrue(
                any("lonely-concept" in item for item in result["orphaned_articles"]["items"])
            )


class VaultStatsTest(unittest.TestCase):
    def test_empty_vault_stats(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            _make_vault(tmpdir)
            stats = vault_stats_sync(tmpdir)
            self.assertEqual(stats["inbox"]["total"], 0)
            self.assertEqual(stats["raw_notes"], 0)
            self.assertEqual(stats["wiki"]["papers"], 0)
            self.assertEqual(stats["compilation_rate"], 0)

    def test_stats_count_sections(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = _make_vault(tmpdir)
            # Add inbox notes
            write_markdown(
                root / "inbox" / "2026-04-05" / "a.md",
                {"paper_id": "doi:a", "status": "approved", "matched_topics": ["vla"]},
                "# A",
            )
            write_markdown(
                root / "inbox" / "2026-04-05" / "b.md",
                {"paper_id": "doi:b", "status": "proposed", "matched_topics": ["manipulation"]},
                "# B",
            )
            # Add raw note
            write_markdown(
                root / "raw" / "notes" / "2026-04-05" / "c.md",
                {"paper_id": "doi:c", "compiled": True, "topics": ["vla"]},
                "# C",
            )
            # Add wiki paper
            write_markdown(
                root / "wiki" / "papers" / "d.md",
                {"citekey": "d", "title": "D", "topics": ["vla"]},
                "# D",
            )
            write_markdown(
                root / "wiki" / "concepts" / "e.md",
                {"concept": "E"},
                "# E",
            )

            stats = vault_stats_sync(tmpdir)
            self.assertEqual(stats["inbox"]["total"], 2)
            self.assertEqual(stats["inbox"]["by_status"]["approved"], 1)
            self.assertEqual(stats["inbox"]["by_status"]["proposed"], 1)
            self.assertEqual(stats["raw_notes"], 1)
            self.assertEqual(stats["compiled"], 1)
            self.assertEqual(stats["compilation_rate"], 1.0)
            self.assertEqual(stats["wiki"]["papers"], 1)
            self.assertEqual(stats["wiki"]["concepts"], 1)
            self.assertIn("vla", stats["by_topic"])


class KnowledgeGraphTest(unittest.TestCase):
    def test_empty_vault_returns_zero_gaps(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            _make_vault(tmpdir)
            result = analyze_knowledge_graph_sync(tmpdir, user_topics=["vla"])
            self.assertEqual(result["paper_count"], 0)
            self.assertEqual(result["concept_count"], 0)

    def test_combination_opportunity_found(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = _make_vault(tmpdir)
            # Two concepts in the same topic but appearing in different papers
            write_markdown(
                root / "wiki" / "concepts" / "method-a.md",
                {"concept": "Method A", "topics": ["robotics"]},
                "# Method A",
            )
            write_markdown(
                root / "wiki" / "concepts" / "method-b.md",
                {"concept": "Method B", "topics": ["robotics"]},
                "# Method B",
            )
            write_markdown(
                root / "wiki" / "papers" / "paper1.md",
                {"citekey": "paper1", "title": "Paper 1", "topics": ["robotics"], "concepts": ["method-a"]},
                "# Paper 1\n\nUses [[concepts/method-a]].",
            )
            write_markdown(
                root / "wiki" / "papers" / "paper2.md",
                {"citekey": "paper2", "title": "Paper 2", "topics": ["robotics"], "concepts": ["method-b"]},
                "# Paper 2\n\nUses [[concepts/method-b]].",
            )

            result = analyze_knowledge_graph_sync(tmpdir, user_topics=["robotics"])
            combos = result["gaps"]["combination_opportunities"]
            self.assertGreater(len(combos), 0)
            pairs = [tuple(c["concept_pair"]) for c in combos]
            self.assertIn(("method-a", "method-b"), pairs)

    def test_methodology_mismatch_found(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = _make_vault(tmpdir)
            # Concept used in "nlp" papers but user works on "vla"
            write_markdown(
                root / "wiki" / "papers" / "nlp1.md",
                {"citekey": "nlp1", "title": "NLP Paper", "topics": ["nlp"], "concepts": ["attention"]},
                "# NLP\n\n[[concepts/attention]]",
            )
            write_markdown(
                root / "wiki" / "papers" / "nlp2.md",
                {"citekey": "nlp2", "title": "NLP Paper 2", "topics": ["nlp"], "concepts": ["attention"]},
                "# NLP2\n\n[[concepts/attention]]",
            )
            write_markdown(
                root / "wiki" / "concepts" / "attention.md",
                {"concept": "Attention", "topics": ["nlp"]},
                "# Attention",
            )

            result = analyze_knowledge_graph_sync(tmpdir, user_topics=["vla"])
            mismatches = result["gaps"]["methodology_mismatches"]
            self.assertGreater(len(mismatches), 0)
            self.assertEqual(mismatches[0]["concept"], "attention")
