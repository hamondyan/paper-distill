"""Tests for the concept registry, maintenance queue, and database modules."""
from __future__ import annotations

import json
import os
import shutil
import tempfile
import unittest

from server.concept_registry import (
    auto_merge_eligible,
    backfill_registry_from_wiki,
    get_concept,
    list_concepts,
    merge_concepts,
    promote_concept,
    register_concept,
    resolve_concept,
    slugify,
    update_paper_count,
)
from server.database import close_db, export_authority_state, get_db, import_authority_state
from server.maintenance import (
    complete_task,
    confirm_task,
    enqueue_task,
    get_pending_tasks,
    reconcile_maintenance_queue,
    reject_task,
)


class _VaultTestBase(unittest.TestCase):
    """Shared setup: temp vault with Paper Distill structure."""

    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.vault_path = self.tmp
        pd_root = os.path.join(self.tmp, "Paper Distill")
        for d in [
            "inbox",
            "raw/source",
            "raw/notes",
            "wiki/papers",
            "wiki/concepts",
            "wiki/methods",
            "wiki/topics",
            "compiled_ir",
            ".state",
        ]:
            os.makedirs(os.path.join(pd_root, d), exist_ok=True)
        # Init DB
        get_db(self.vault_path)

    def tearDown(self):
        close_db(self.vault_path)
        shutil.rmtree(self.tmp)

    def _write_concept_file(self, name: str, paper_count: int = 0, aliases: list | None = None):
        """Create a wiki/concepts/{slug}.md file with valid frontmatter."""
        slug = slugify(name)
        fm_parts = [
            "---",
            f"concept: {name}",
            f"paper_count: {paper_count}",
        ]
        if aliases:
            fm_parts.append(f"aliases: {json.dumps(aliases)}")
        fm_parts.extend(["---", "", f"# {name}", ""])
        path = os.path.join(self.tmp, "Paper Distill", "wiki", "concepts", f"{slug}.md")
        with open(path, "w") as f:
            f.write("\n".join(fm_parts))
        return path

    def _write_paper_file(self, citekey: str, concepts: list | None = None, wikilinks: list | None = None):
        """Create a wiki/papers/{citekey}.md file."""
        fm_parts = [
            "---",
            f"citekey: {citekey}",
            f"title: Paper {citekey}",
        ]
        if concepts:
            fm_parts.append(f"concepts: {json.dumps(concepts)}")
        fm_parts.extend(["---", ""])
        if wikilinks:
            for wl in wikilinks:
                fm_parts.append(f"See [[{wl}]]")
        fm_parts.append("")
        path = os.path.join(self.tmp, "Paper Distill", "wiki", "papers", f"{citekey}.md")
        with open(path, "w") as f:
            f.write("\n".join(fm_parts))
        return path


# ============================================================================
# Slugify
# ============================================================================

class SlugifyTest(unittest.TestCase):
    def test_basic(self):
        assert slugify("Diffusion Policy") == "diffusion-policy"

    def test_special_chars(self):
        assert slugify("Vision-Language-Action Models") == "vision-language-action-models"

    def test_extra_spaces(self):
        assert slugify("  Hello   World  ") == "hello-world"

    def test_empty(self):
        assert slugify("") == ""


# ============================================================================
# Auto-merge eligibility
# ============================================================================

class AutoMergeTest(unittest.TestCase):
    def test_slug_match(self):
        reason = auto_merge_eligible("Diffusion Policy", "diffusion policy")
        assert reason == "slug_match"

    def test_abbreviation_whitelist(self):
        reason = auto_merge_eligible("VLA", "Vision-Language-Action")
        assert reason is not None
        assert "abbreviation_whitelist" in reason

    def test_spelling_variant(self):
        reason = auto_merge_eligible("Behavioral Cloning", "Behavioural Cloning")
        assert reason == "spelling_variant"

    def test_not_eligible(self):
        reason = auto_merge_eligible("Diffusion Policy", "Reinforcement Learning")
        assert reason is None

    def test_case_insensitive_abbreviation(self):
        reason = auto_merge_eligible("llm", "Large Language Model")
        assert reason is not None


# ============================================================================
# Registry CRUD
# ============================================================================

class RegisterConceptTest(_VaultTestBase):
    def test_register_new(self):
        result = register_concept(self.vault_path, "Diffusion Policy")
        assert result["created"] is True
        assert result["id"] == "diffusion-policy"
        assert result["canonical"] == "Diffusion Policy"

    def test_register_duplicate_returns_existing(self):
        register_concept(self.vault_path, "Diffusion Policy")
        result = register_concept(self.vault_path, "diffusion policy")
        assert result["created"] is False
        assert result["id"] == "diffusion-policy"

    def test_register_with_aliases(self):
        register_concept(
            self.vault_path, "Vision-Language-Action Models",
            aliases=["VLA", "VLA model"],
        )
        resolved = resolve_concept(self.vault_path, "VLA")
        assert resolved is not None
        assert resolved["id"] == "vision-language-action-models"

    def test_auto_merge_on_register(self):
        register_concept(self.vault_path, "Vision-Language-Action")
        result = register_concept(self.vault_path, "VLA")
        assert result["created"] is False
        assert result["merged_into"] == "vision-language-action"

    def test_register_method_type(self):
        result = register_concept(self.vault_path, "PPO", concept_type="method")
        assert result["type"] == "method"


class ResolveConceptTest(_VaultTestBase):
    def test_resolve_by_alias(self):
        register_concept(self.vault_path, "Diffusion Policy", aliases=["DP"])
        result = resolve_concept(self.vault_path, "DP")
        assert result is not None
        assert result["id"] == "diffusion-policy"

    def test_resolve_by_slug(self):
        register_concept(self.vault_path, "Diffusion Policy")
        result = resolve_concept(self.vault_path, "diffusion-policy")
        assert result is not None

    def test_resolve_by_abbreviation_expansion(self):
        register_concept(self.vault_path, "Reinforcement Learning")
        result = resolve_concept(self.vault_path, "RL")
        assert result is not None
        assert result["id"] == "reinforcement-learning"

    def test_resolve_not_found(self):
        result = resolve_concept(self.vault_path, "nonexistent")
        assert result is None


class MergeConceptsTest(_VaultTestBase):
    def test_merge_success(self):
        register_concept(self.vault_path, "Concept A")
        register_concept(self.vault_path, "Concept B")
        update_paper_count(self.vault_path, "concept-a", 3)
        update_paper_count(self.vault_path, "concept-b", 5)

        result = merge_concepts(self.vault_path, "concept-a", "concept-b", "testing merge")
        assert result["merged"] is True
        assert result["paper_count"] == 8

        # concept-a should resolve to concept-b now
        resolved = resolve_concept(self.vault_path, "Concept A")
        assert resolved is not None
        assert resolved["id"] == "concept-b"

    def test_merge_nonexistent_source(self):
        register_concept(self.vault_path, "Concept B")
        result = merge_concepts(self.vault_path, "nonexistent", "concept-b")
        assert "error" in result

    def test_merge_recorded_in_history(self):
        register_concept(self.vault_path, "Concept A")
        register_concept(self.vault_path, "Concept B")
        merge_concepts(self.vault_path, "concept-a", "concept-b", "test reason")

        conn = get_db(self.vault_path)
        rows = conn.execute("SELECT * FROM concept_merge_history").fetchall()
        assert len(rows) == 1
        assert rows[0]["from_concept"] == "concept-a"
        assert rows[0]["to_concept"] == "concept-b"
        assert rows[0]["reason"] == "test reason"


class ListConceptsTest(_VaultTestBase):
    def test_list_all(self):
        register_concept(self.vault_path, "Concept A")
        register_concept(self.vault_path, "Concept B", concept_type="method")
        concepts = list_concepts(self.vault_path)
        assert len(concepts) == 2

    def test_list_filtered_by_type(self):
        register_concept(self.vault_path, "Concept A")
        register_concept(self.vault_path, "Method B", concept_type="method")
        concepts = list_concepts(self.vault_path, concept_type="method")
        assert len(concepts) == 1
        assert concepts[0]["id"] == "method-b"


class PromoteConceptTest(_VaultTestBase):
    def test_promote(self):
        register_concept(self.vault_path, "Diffusion Policy")
        result = promote_concept(self.vault_path, "diffusion-policy")
        assert result["promoted"] is True
        assert result["new_type"] == "topic"

        concept = get_concept(self.vault_path, "diffusion-policy")
        assert concept["type"] == "topic"
        assert concept["promoted"] == 1


# ============================================================================
# Maintenance Queue
# ============================================================================

class ReconcileTest(_VaultTestBase):
    def test_creates_tasks_from_lint(self):
        lint_results = {
            "semantic_duplicates": {
                "count": 1,
                "items": [
                    {"file_a": "a.md", "title_a": "Paper A", "file_b": "b.md", "title_b": "Paper B", "similarity": 0.8}
                ],
            },
            "orphaned_articles": {"count": 1, "items": ["wiki/concepts/orphan.md"]},
            "missing_concept_stubs": {"count": 1, "items": ["concepts/stub-concept"]},
        }
        result = reconcile_maintenance_queue(
            self.vault_path, lint_results=lint_results, auto_confirm=False,
        )
        assert result["created"] == 3
        tasks = get_pending_tasks(self.vault_path)
        assert len(tasks) == 3
        assert any(task["task_type"] == "paper_duplicate_review" for task in tasks)

    def test_deduplicates_on_second_run(self):
        lint_results = {
            "orphaned_articles": {"count": 1, "items": ["wiki/concepts/orphan.md"]},
        }
        reconcile_maintenance_queue(self.vault_path, lint_results=lint_results)
        result = reconcile_maintenance_queue(self.vault_path, lint_results=lint_results)
        assert result["created"] == 0
        assert result["skipped_duplicate"] == 1

    def test_creates_promotion_tasks_from_stats(self):
        stats_results = {
            "promotion_candidates": [
                {"concept": "diffusion-policy", "paper_count": 7},
            ],
            "stale_topics": [
                {"topic": "robotics", "new_paper_count": 5, "reasons": ["5 new papers"]},
            ],
        }
        result = reconcile_maintenance_queue(self.vault_path, stats_results=stats_results)
        assert result["created"] == 2


class TaskLifecycleTest(_VaultTestBase):
    def test_confirm_and_complete(self):
        lint_results = {"orphaned_articles": {"count": 1, "items": ["x.md"]}}
        reconcile_maintenance_queue(self.vault_path, lint_results=lint_results)

        tasks = get_pending_tasks(self.vault_path, status="pending")
        assert len(tasks) == 1
        task_id = tasks[0]["id"]

        confirm_task(self.vault_path, task_id)
        tasks = get_pending_tasks(self.vault_path, status="confirmed")
        assert len(tasks) == 1

        complete_task(self.vault_path, task_id)
        tasks = get_pending_tasks(self.vault_path, status="done")
        assert len(tasks) == 1

        # No longer in active list
        active = get_pending_tasks(self.vault_path)
        assert len(active) == 0

    def test_reject(self):
        lint_results = {"orphaned_articles": {"count": 1, "items": ["x.md"]}}
        reconcile_maintenance_queue(self.vault_path, lint_results=lint_results)

        tasks = get_pending_tasks(self.vault_path, status="pending")
        task_id = tasks[0]["id"]

        reject_task(self.vault_path, task_id, "not needed")
        active = get_pending_tasks(self.vault_path)
        assert len(active) == 0

    def test_enqueue_manual_merge_task(self):
        result = enqueue_task(
            self.vault_path,
            "merge_candidate",
            {"from_id": "concept-a", "to_id": "concept-b", "reason": "manual adjudication"},
            status="confirmed",
        )
        assert result["created"] is True
        tasks = get_pending_tasks(self.vault_path, status="confirmed")
        assert len(tasks) == 1
        assert tasks[0]["task_type"] == "merge_candidate"


# ============================================================================
# Database export/import
# ============================================================================

class ExportImportTest(_VaultTestBase):
    def test_export_import_roundtrip(self):
        register_concept(self.vault_path, "Concept A")
        register_concept(self.vault_path, "Concept B", aliases=["CB"])

        exported = export_authority_state(self.vault_path)
        assert len(exported["concept_registry"]) == 2
        assert len(exported["concept_aliases"]) >= 2

        # Create a fresh vault and import
        tmp2 = tempfile.mkdtemp()
        try:
            pd_root2 = os.path.join(tmp2, "Paper Distill", ".state")
            os.makedirs(pd_root2, exist_ok=True)
            counts = import_authority_state(tmp2, exported)
            assert counts["concept_registry"] == 2

            # Verify data is there
            concepts = list_concepts(tmp2)
            assert len(concepts) == 2
        finally:
            close_db(tmp2)
            shutil.rmtree(tmp2)


# ============================================================================
# Backfill
# ============================================================================

class BackfillTest(_VaultTestBase):
    def test_backfill_from_wiki(self):
        self._write_concept_file("Diffusion Policy", paper_count=3)
        self._write_concept_file("Reinforcement Learning", paper_count=5)
        self._write_paper_file(
            "smith2024",
            concepts=["Diffusion Policy"],
            wikilinks=["concepts/reinforcement-learning"],
        )

        result = backfill_registry_from_wiki(self.vault_path)
        assert result["concepts_registered"] == 2
        assert result["papers_indexed"] == 1
        assert result["deps_created"] >= 1

        # Verify concepts are in registry
        dp = resolve_concept(self.vault_path, "Diffusion Policy")
        assert dp is not None
        assert dp["id"] == "diffusion-policy"

        # Verify compile_state
        conn = get_db(self.vault_path)
        state = conn.execute(
            "SELECT * FROM compile_state WHERE page_id = 'smith2024'"
        ).fetchone()
        assert state is not None
        assert state["schema_version"] == "legacy"


if __name__ == "__main__":
    unittest.main()
