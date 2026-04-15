"""Tests for the unified CRGP compile path with metadata / IR integration.

Covers four scenarios from the implementation plan:

    1. save_with_metadata_creates_ir_files
       – IR JSON and resolved IR are written; compile_state.ir_path is set.

    2. save_without_metadata_is_backward_compatible
       – No IR files are created; compile_state.ir_path remains NULL; no
         ir_warnings key in the result.

    3. save_with_invalid_metadata_still_writes_wiki
       – When the metadata fails IR validation, the wiki page is still written
         and the result contains an ir_warnings list.

    4. tension_signals_sees_crgp_paper_after_unified_save
       – After a save+metadata call, aggregate_tension_signals() counts the
         paper and returns its limitations.
"""
from __future__ import annotations

import json
import os
import shutil
import tempfile
import unittest

from server.compile_ir import aggregate_tension_signals, get_compile_state
from server.crgp_tools import save_crgp_sections
from server.database import close_db, get_db


# ---------------------------------------------------------------------------
# Shared fixtures
# ---------------------------------------------------------------------------

_SECTIONS = {
    "Context": "Context text.",
    "Related Work": "Related work text.",
    "Gap": "Gap text.",
    "Proposal": "Proposal text.",
    "Key Results": "Key results text.",
    "Discussion": "Discussion text.",
    "Next Steps": "Next steps text.",
}

_METADATA = {
    "candidate_concepts": [
        {"name": "Diffusion Policy", "type": "method"},
        {"name": "Vision-Language-Action Models", "type": "concept", "aliases": ["VLA"]},
    ],
    "tension_fields": {
        "limitations": [
            {"claim": "Only tested in tabletop environments", "source_ref": "sources/evidence/test2024/section-6"},
        ],
        "assumptions": [
            {"claim": "Assumes large pre-training dataset availability"},
        ],
        "open_questions": [
            {"question": "Does this scale to dexterous manipulation?"},
        ],
        "negative_results": [],
        "failure_modes": [{"claim": "Fails under heavy occlusion"}],
        "transfer_constraints": [],
    },
    "benchmark_scope": "Tabletop manipulation",
    "claimed_novelty": "First unified diffusion + VLA policy",
}

# Minimal source evidence frontmatter — the file format expected by
# crgp_tools._read_frontmatter: starts with "---\n", YAML block, "\n---\n", body.
_SOURCE_EVIDENCE_CONTENT = """\
---
citekey: test2024
paper_id: arxiv:2401.00001
title: A Test Paper on Unified Compile
authors:
  - Doe, Jane
  - Roe, John
year: 2024
doi: ""
arxiv_id: "2401.00001"
venue: ICRA
venue_normalized: ICRA
venue_tier: A
venue_source: manual
topics:
  - manipulation
canonical_html_url: https://arxiv.org/abs/2401.00001
canonical_pdf_url: https://arxiv.org/pdf/2401.00001
canonical_item_url: ""
source_structured_path: ""
capture_fidelity: full

---

## Abstract
This is a test abstract.
"""


def _make_vault(tmp: str, citekey: str = "test2024") -> str:
    """Create the minimal vault directory tree and source evidence file."""
    pd_root = os.path.join(tmp, "Paper Distill")
    for d in [
        ".state",
        ".state/ir",
        "wiki/papers",
        "wiki/concepts",
        "wiki/methods",
        "wiki/topics",
        f"sources/evidence/{citekey}",
    ]:
        os.makedirs(os.path.join(pd_root, d), exist_ok=True)

    # Write source evidence file
    evidence_path = os.path.join(pd_root, "sources", "evidence", f"{citekey}.md")
    with open(evidence_path, "w", encoding="utf-8") as f:
        f.write(_SOURCE_EVIDENCE_CONTENT)

    get_db(tmp)  # initialise SQLite schema
    return tmp


# ---------------------------------------------------------------------------
# Base class
# ---------------------------------------------------------------------------

class _VaultBase(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        _make_vault(self.tmp)

    def tearDown(self):
        close_db(self.tmp)
        shutil.rmtree(self.tmp)

    # helpers
    def _ir_path(self, citekey: str, resolved: bool = False) -> str:
        suffix = "_resolved.json" if resolved else ".json"
        return os.path.join(
            self.tmp, "Paper Distill", ".state", "ir", f"{citekey}{suffix}"
        )

    def _wiki_path(self, citekey: str) -> str:
        return os.path.join(
            self.tmp, "Paper Distill", "wiki", "papers", f"{citekey}.md"
        )


# ---------------------------------------------------------------------------
# Test 1: save + metadata creates IR files and records ir_path
# ---------------------------------------------------------------------------

class SaveWithMetadataTest(_VaultBase):
    def test_wiki_page_is_written(self):
        result = save_crgp_sections(
            self.tmp, "test2024", _SECTIONS, metadata=_METADATA
        )
        self.assertTrue(result.get("written"), msg=result)
        self.assertTrue(os.path.exists(self._wiki_path("test2024")))

    def test_raw_ir_file_is_created(self):
        save_crgp_sections(self.tmp, "test2024", _SECTIONS, metadata=_METADATA)
        self.assertTrue(
            os.path.exists(self._ir_path("test2024", resolved=False)),
            "Expected .state/ir/test2024.json to be created",
        )

    def test_resolved_ir_file_is_created(self):
        save_crgp_sections(self.tmp, "test2024", _SECTIONS, metadata=_METADATA)
        self.assertTrue(
            os.path.exists(self._ir_path("test2024", resolved=True)),
            "Expected .state/ir/test2024_resolved.json to be created",
        )

    def test_compile_state_ir_path_is_set(self):
        save_crgp_sections(self.tmp, "test2024", _SECTIONS, metadata=_METADATA)
        state = get_compile_state(self.tmp, "test2024", "paper")
        self.assertIsNotNone(state, "compile_state row should exist")
        self.assertIsNotNone(
            state["ir_path"],
            "compile_state.ir_path should be set after save+metadata",
        )
        self.assertIn("_resolved.json", state["ir_path"])

    def test_no_ir_warnings_on_valid_metadata(self):
        result = save_crgp_sections(
            self.tmp, "test2024", _SECTIONS, metadata=_METADATA
        )
        self.assertNotIn(
            "ir_warnings", result,
            "Valid metadata should produce no ir_warnings",
        )

    def test_raw_ir_contains_tension_fields(self):
        save_crgp_sections(self.tmp, "test2024", _SECTIONS, metadata=_METADATA)
        with open(self._ir_path("test2024"), encoding="utf-8") as f:
            ir = json.load(f)
        self.assertIn("tension_fields", ir)
        self.assertIn("limitations", ir["tension_fields"])
        self.assertEqual(len(ir["tension_fields"]["limitations"]), 1)

    def test_resolved_ir_contains_resolutions(self):
        save_crgp_sections(self.tmp, "test2024", _SECTIONS, metadata=_METADATA)
        with open(self._ir_path("test2024", resolved=True), encoding="utf-8") as f:
            ir = json.load(f)
        self.assertTrue(ir.get("_resolved"))
        self.assertIsInstance(ir.get("_resolutions"), list)
        self.assertGreater(len(ir["_resolutions"]), 0)


# ---------------------------------------------------------------------------
# Test 2: save WITHOUT metadata is fully backward-compatible
# ---------------------------------------------------------------------------

class SaveWithoutMetadataTest(_VaultBase):
    def test_wiki_page_is_still_written(self):
        result = save_crgp_sections(self.tmp, "test2024", _SECTIONS)
        self.assertTrue(result.get("written"), msg=result)
        self.assertTrue(os.path.exists(self._wiki_path("test2024")))

    def test_no_ir_files_created(self):
        save_crgp_sections(self.tmp, "test2024", _SECTIONS)
        self.assertFalse(
            os.path.exists(self._ir_path("test2024", resolved=False)),
            "No raw IR file should exist when metadata is omitted",
        )
        self.assertFalse(
            os.path.exists(self._ir_path("test2024", resolved=True)),
            "No resolved IR file should exist when metadata is omitted",
        )

    def test_compile_state_ir_path_is_null(self):
        save_crgp_sections(self.tmp, "test2024", _SECTIONS)
        state = get_compile_state(self.tmp, "test2024", "paper")
        self.assertIsNotNone(state)
        self.assertIsNone(
            state["ir_path"],
            "compile_state.ir_path should be NULL when no metadata provided",
        )

    def test_no_ir_warnings_key_in_result(self):
        result = save_crgp_sections(self.tmp, "test2024", _SECTIONS)
        self.assertNotIn("ir_warnings", result)


# ---------------------------------------------------------------------------
# Test 3: save with INVALID metadata still writes wiki, returns ir_warnings
# ---------------------------------------------------------------------------

class SaveWithInvalidMetadataTest(_VaultBase):
    """When metadata fails IR validation, the wiki page is still written."""

    _INVALID_METADATA = {
        # candidate_concepts present but tension_fields missing required subkeys
        "candidate_concepts": [{"name": "Foo", "type": "concept"}],
        "tension_fields": {
            "limitations": [],
            # missing: assumptions, open_questions, negative_results
        },
    }

    def test_wiki_page_written_despite_ir_failure(self):
        result = save_crgp_sections(
            self.tmp, "test2024", _SECTIONS, metadata=self._INVALID_METADATA
        )
        self.assertTrue(
            result.get("written"),
            "Wiki page should be written even when IR validation fails",
        )
        self.assertTrue(os.path.exists(self._wiki_path("test2024")))

    def test_ir_warnings_present_in_result(self):
        result = save_crgp_sections(
            self.tmp, "test2024", _SECTIONS, metadata=self._INVALID_METADATA
        )
        self.assertIn("ir_warnings", result, "Should return ir_warnings on IR failure")
        self.assertIsInstance(result["ir_warnings"], list)
        self.assertGreater(len(result["ir_warnings"]), 0)

    def test_no_ir_files_created_on_validation_failure(self):
        save_crgp_sections(
            self.tmp, "test2024", _SECTIONS, metadata=self._INVALID_METADATA
        )
        self.assertFalse(
            os.path.exists(self._ir_path("test2024", resolved=False)),
            "Raw IR file must not be created when validation fails",
        )

    def test_compile_state_ir_path_null_on_validation_failure(self):
        save_crgp_sections(
            self.tmp, "test2024", _SECTIONS, metadata=self._INVALID_METADATA
        )
        state = get_compile_state(self.tmp, "test2024", "paper")
        self.assertIsNotNone(state)
        self.assertIsNone(state["ir_path"])


# ---------------------------------------------------------------------------
# Test 4: aggregate_tension_signals sees the paper after unified save
# ---------------------------------------------------------------------------

class TensionSignalsIntegrationTest(_VaultBase):
    """After save+metadata, idea-analyze can pick up the paper's tension signals."""

    def test_papers_scanned_count_includes_crgp_paper(self):
        save_crgp_sections(self.tmp, "test2024", _SECTIONS, metadata=_METADATA)
        result = aggregate_tension_signals(self.tmp, min_occurrence=1)
        self.assertEqual(
            result["papers_scanned"], 1,
            "aggregate_tension_signals should count the CRGP-compiled paper",
        )

    def test_recurring_limitations_includes_crgp_limitation(self):
        save_crgp_sections(self.tmp, "test2024", _SECTIONS, metadata=_METADATA)
        result = aggregate_tension_signals(self.tmp, min_occurrence=1)
        # At least one keyword from "Only tested in tabletop environments"
        # should appear in recurring_limitations
        keywords = [item["keyword"] for item in result.get("recurring_limitations", [])]
        self.assertTrue(
            len(keywords) > 0,
            f"Expected recurring_limitations from paper, got: {result}",
        )

    def test_paper_without_metadata_is_invisible_to_tension_signals(self):
        """Regression: a paper compiled without metadata should not be scanned."""
        save_crgp_sections(self.tmp, "test2024", _SECTIONS)  # no metadata
        result = aggregate_tension_signals(self.tmp, min_occurrence=1)
        self.assertEqual(
            result["papers_scanned"], 0,
            "Papers compiled without metadata should not appear in tension signals",
        )

    def test_two_papers_trigger_min_occurrence_2(self):
        """Two papers sharing a limitation keyword satisfy min_occurrence=2."""
        # Paper 1: test2024 already has "tabletop" in limitations
        save_crgp_sections(self.tmp, "test2024", _SECTIONS, metadata=_METADATA)

        # Paper 2: second paper with overlapping keyword — write evidence separately
        second_citekey = "another2024"
        pd_root = os.path.join(self.tmp, "Paper Distill")
        os.makedirs(os.path.join(pd_root, "sources", "evidence", second_citekey), exist_ok=True)
        evidence_path = os.path.join(pd_root, "sources", "evidence", f"{second_citekey}.md")
        with open(evidence_path, "w", encoding="utf-8") as f:
            f.write(_SOURCE_EVIDENCE_CONTENT.replace("test2024", second_citekey))

        second_metadata = {
            **_METADATA,
            "tension_fields": {
                **_METADATA["tension_fields"],
                "limitations": [
                    {"claim": "Only tested in tabletop manipulation scenarios"},
                ],
            },
        }
        save_crgp_sections(self.tmp, second_citekey, _SECTIONS, metadata=second_metadata)

        result = aggregate_tension_signals(self.tmp, min_occurrence=2)
        self.assertEqual(result["papers_scanned"], 2)
        keywords = [item["keyword"] for item in result.get("recurring_limitations", [])]
        # "tabletop" appears in both limitations → should surface at min_occurrence=2
        self.assertIn(
            "tabletop", keywords,
            f"'tabletop' should be a recurring limitation keyword. Got: {keywords}",
        )


if __name__ == "__main__":
    unittest.main()
