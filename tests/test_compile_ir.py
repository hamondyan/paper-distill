"""Tests for compile_ir.py — the EDC pipeline intermediate representation."""
from __future__ import annotations

import json
import os
import shutil
import tempfile
import unittest

from server.concept_registry import register_concept
from server.database import close_db, get_db
from server.compile_ir import (
    aggregate_tension_signals,
    commit_compile_result,
    get_compile_state,
    resolve_ir,
    validate_ir,
    write_ir,
)


_MINIMAL_IR = {
    "citekey": "smith2024",
    "title": "A Paper on Robots",
    "authors": ["Smith, J."],
    "candidate_concepts": [
        {"name": "Diffusion Policy", "type": "method"},
    ],
    "benchmark_scope": "Tabletop manipulation only",
    "claimed_novelty": "First VLA adaptation to constrained tabletop tasks",
    "tension_fields": {
        "limitations": [{"claim": "Only tested in simulation environments", "source_ref": "raw/source/smith2024/section-6"}],
        "assumptions": [{"claim": "Requires large training datasets", "source_ref": "raw/source/smith2024/section-2"}],
        "failure_modes": [{"claim": "Fails when more than three objects occlude the goal", "source_ref": "raw/source/smith2024/table-4"}],
        "transfer_constraints": [{"claim": "Sim-to-real transfer was not evaluated", "source_ref": "raw/source/smith2024/section-7"}],
        "open_questions": [{"question": "How does this scale to real robots?", "source_ref": "raw/source/smith2024/section-8"}],
        "negative_results": [],
    },
}


class _VaultBase(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        pd_root = os.path.join(self.tmp, "Paper Distill")
        for d in ["compiled_ir", ".state", "wiki/papers", "wiki/concepts", "wiki/methods", "wiki/topics"]:
            os.makedirs(os.path.join(pd_root, d), exist_ok=True)
        get_db(self.tmp)

    def tearDown(self):
        close_db(self.tmp)
        shutil.rmtree(self.tmp)


# ============================================================================
# Validation
# ============================================================================

class ValidateIRTest(unittest.TestCase):
    def test_valid_ir_no_errors(self):
        errors = validate_ir(_MINIMAL_IR)
        assert errors == []

    def test_missing_citekey(self):
        ir = {**_MINIMAL_IR}
        del ir["citekey"]
        errors = validate_ir(ir)
        assert any("citekey" in e for e in errors)

    def test_missing_tension_fields(self):
        ir = {**_MINIMAL_IR}
        del ir["tension_fields"]
        errors = validate_ir(ir)
        assert any("tension_fields" in e for e in errors)

    def test_missing_tension_subkey(self):
        ir = {**_MINIMAL_IR, "tension_fields": {"limitations": [], "assumptions": []}}
        errors = validate_ir(ir)
        assert any("open_questions" in e for e in errors)

    def test_tension_fields_not_dict(self):
        ir = {**_MINIMAL_IR, "tension_fields": "not a dict"}
        errors = validate_ir(ir)
        assert any("tension_fields" in e for e in errors)

    def test_invalid_source_ref_type(self):
        ir = json.loads(json.dumps(_MINIMAL_IR))
        ir["tension_fields"]["limitations"][0]["source_ref"] = 123
        errors = validate_ir(ir)
        assert any("source_ref" in e for e in errors)


# ============================================================================
# Write / Read IR
# ============================================================================

class WriteIRTest(_VaultBase):
    def test_write_valid_ir(self):
        result = write_ir(self.tmp, "smith2024", _MINIMAL_IR)
        assert result["valid"] is True
        assert result["errors"] == []
        assert "smith2024.json" in result["path"]

        # File should exist
        path = os.path.join(self.tmp, "Paper Distill", "compiled_ir", "smith2024.json")
        assert os.path.exists(path)

        stored = json.loads(open(path).read())
        assert stored["citekey"] == "smith2024"
        assert stored["schema_version"] == "2024-06"

    def test_write_invalid_ir_rejected(self):
        bad_ir = {"citekey": "x"}  # missing required fields
        result = write_ir(self.tmp, "x", bad_ir)
        assert result["valid"] is False
        assert len(result["errors"]) > 0


# ============================================================================
# Resolve IR (entity linking)
# ============================================================================

class ResolveIRTest(_VaultBase):
    def test_resolve_registers_new_concept(self):
        write_ir(self.tmp, "smith2024", _MINIMAL_IR)
        result = resolve_ir(self.tmp, "smith2024")
        assert "error" not in result
        assert result["resolved_count"] == 1
        assert result["registered_new"] == 1

        # Resolved JSON should exist
        resolved_path = os.path.join(
            self.tmp, "Paper Distill", "compiled_ir", "smith2024_resolved.json"
        )
        assert os.path.exists(resolved_path)
        resolved = json.loads(open(resolved_path).read())
        assert resolved["_resolved"] is True
        assert len(resolved["_resolutions"]) == 1
        assert resolved["_resolutions"][0]["canonical_id"] == "diffusion-policy"

    def test_resolve_reuses_existing_concept(self):
        register_concept(self.tmp, "Diffusion Policy", "method")
        write_ir(self.tmp, "smith2024", _MINIMAL_IR)
        result = resolve_ir(self.tmp, "smith2024")
        assert result["registered_new"] == 0  # already exists
        assert result["resolved_count"] == 1

    def test_resolve_missing_ir_returns_error(self):
        result = resolve_ir(self.tmp, "nonexistent")
        assert "error" in result


# ============================================================================
# Aggregate tension signals
# ============================================================================

class AggregateTensionTest(_VaultBase):
    def _write_resolved(self, citekey: str, limitations: list, open_questions: list):
        """Write a synthetic resolved IR directly."""
        ir = {
            "citekey": citekey,
            "benchmark_scope": "tabletop only",
            "claimed_novelty": "Novel attention head",
            "tension_fields": {
                "limitations": limitations,
                "assumptions": [],
                "failure_modes": [],
                "transfer_constraints": [],
                "open_questions": open_questions,
                "negative_results": [],
            },
            "_resolved": True,
            "_resolutions": [],
        }
        path = os.path.join(
            self.tmp, "Paper Distill", "compiled_ir", f"{citekey}_resolved.json"
        )
        with open(path, "w") as f:
            json.dump(ir, f)

    def test_empty_dir_returns_zero(self):
        result = aggregate_tension_signals(self.tmp)
        assert result["papers_scanned"] == 0
        assert result["recurring_limitations"] == []

    def test_recurring_limitation_detected(self):
        self._write_resolved("p1", [{"claim": "simulation only tested small scale"}], [])
        self._write_resolved("p2", [{"claim": "simulation only tested small scale"}], [])
        result = aggregate_tension_signals(self.tmp, min_occurrence=2)
        assert result["papers_scanned"] == 2
        # "simulation" and "small" and "scale" and "tested" and "only" appear in both
        recurring_kws = {r["keyword"] for r in result["recurring_limitations"]}
        assert len(recurring_kws) > 0

    def test_open_question_clustering(self):
        self._write_resolved("p1", [], [{"question": "Can this scale to real robots?"}])
        self._write_resolved("p2", [], [{"question": "Can scaling work with real robots?"}])
        result = aggregate_tension_signals(self.tmp)
        assert result["papers_scanned"] == 2
        assert len(result["open_question_clusters"]) > 0

    def test_collects_benchmark_scope_and_claimed_novelty(self):
        self._write_resolved("p1", [], [])
        result = aggregate_tension_signals(self.tmp)
        assert len(result["benchmark_scopes"]) == 1
        assert len(result["claimed_novelties"]) == 1


# ============================================================================
# Commit compile result
# ============================================================================

class CommitCompileResultTest(_VaultBase):
    def test_commit_writes_file_and_db(self):
        content = "<!-- managed:start -->\n## Context\nSome content.\n<!-- managed:end -->"
        fm = {"citekey": "smith2024", "title": "A Paper", "compile_version": 1}
        result = commit_compile_result(
            self.tmp, "smith2024", "paper", content, fm,
        )
        assert result["written"] is True
        assert "smith2024.md" in result["path"]
        assert os.path.exists(result["path"])

        state = get_compile_state(self.tmp, "smith2024", "paper")
        assert state is not None
        assert state["schema_version"] == "2024-06"
        assert state["content_hash"] is not None

    def test_commit_increments_version(self):
        content = "Body"
        fm = {"citekey": "smith2024", "title": "A Paper", "compile_version": 1}
        r1 = commit_compile_result(self.tmp, "smith2024", "paper", content, fm)
        r2 = commit_compile_result(self.tmp, "smith2024", "paper", content, fm)
        assert r2["compile_version"] == r1["compile_version"] + 1

    def test_commit_writes_deps(self):
        register_concept(self.tmp, "Diffusion Policy", "method")
        deps = [{"dep_type": "concept", "dep_id": "diffusion-policy", "dep_version": 1}]
        result = commit_compile_result(
            self.tmp, "jones2023", "paper", "content", {"citekey": "jones2023"}, deps=deps,
        )
        assert result["written"] is True

        conn = get_db(self.tmp)
        row = conn.execute(
            "SELECT * FROM compile_deps WHERE page_id = 'jones2023'"
        ).fetchone()
        assert row is not None
        assert row["dep_id"] == "diffusion-policy"

    def test_commit_invalid_page_type(self):
        result = commit_compile_result(
            self.tmp, "x", "invalid_type", "content", {},
        )
        assert "error" in result


if __name__ == "__main__":
    unittest.main()
