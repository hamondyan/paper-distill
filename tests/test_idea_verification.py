from __future__ import annotations

import json
import shutil
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import yaml

from server.database import close_db
from server.idea_verification import verify_idea
from server.runtime import get_mutation_record
from server.vault_contract import root_path
from server.vault_ops import ensure_vault_structure, write_markdown as vault_write_markdown


def _read_frontmatter(path: Path) -> dict:
    content = path.read_text(encoding="utf-8")
    _, remainder = content.split("---\n", 1)
    fm_text, _ = remainder.split("\n---\n", 1)
    return yaml.safe_load(fm_text) or {}


class IdeaVerificationRuntimeTest(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.mkdtemp()
        ensure_vault_structure(self.tmp)

    def tearDown(self) -> None:
        close_db(self.tmp)
        shutil.rmtree(self.tmp)

    def _idea_payload(self) -> dict:
        return {
            "idea_id": "embodied-active-labeling",
            "title": "Embodied active labeling for long-horizon manipulation",
            "summary": "Use failure-aware active labeling to target rare long-horizon failures.",
            "hypothesis": "Selective relabeling could make long-horizon failures cheaper to fix.",
            "local_evidence": {
                "wiki": [
                    {
                        "ref": "Paper Distill/wiki/topics/manipulation.md",
                        "summary": "Long-horizon manipulation failures recur across multiple papers.",
                    }
                ],
                "sources": [
                    {
                        "ref": "Paper Distill/sources/notes/2026-04-08/fixture.md",
                        "summary": "Source notes highlight rare recovery failures after occlusion.",
                    }
                ],
                "memory": [
                    {
                        "view_key": "taste",
                        "summary": "User cares more about real failure analysis than benchmark deltas.",
                    }
                ],
            },
        }

    def test_verified_idea_persists_snapshot_and_promotes_durable_memo(self) -> None:
        result = verify_idea(
            self.tmp,
            idea=self._idea_payload(),
            verification={
                "queries": [
                    "active labeling manipulation long horizon failure analysis",
                    "rare failure relabeling robotics",
                ],
                "required_providers": ["web-search", "papers-with-code"],
                "providers": [
                    {
                        "provider": "web-search",
                        "status": "succeeded",
                        "query": "active labeling manipulation long horizon failure analysis",
                        "evidence": [
                            {
                                "title": "Failure-aware data selection for robotics",
                                "url": "https://example.com/failure-aware-data-selection",
                                "stance": "supporting",
                                "excerpt": "x" * 500,
                            }
                        ],
                    },
                    {
                        "provider": "papers-with-code",
                        "status": "succeeded",
                        "query": "rare failure relabeling robotics",
                        "evidence": [
                            {
                                "title": "Benchmark gaps in long-horizon recovery",
                                "url": "https://example.com/benchmark-gaps",
                                "stance": "supporting",
                                "excerpt": "Recovery failures remain under-evaluated in current benchmarks.",
                            }
                        ],
                    },
                ],
                "notes": "Both providers found adjacent evidence, and neither introduced contradictions.",
            },
        )

        self.assertTrue(result["ok"])
        self.assertTrue(result["snapshot_persisted"])
        self.assertTrue(result["promoted"])
        self.assertEqual(result["idea_state"], "durable")
        self.assertEqual(result["verification_state"], "verified")

        snapshot_path = Path(result["snapshot_path"])
        self.assertTrue(snapshot_path.exists())
        snapshot = json.loads(snapshot_path.read_text(encoding="utf-8"))
        self.assertEqual(snapshot["verification_state"], "verified")
        self.assertTrue(snapshot["promotion_eligible"])
        self.assertEqual(snapshot["trust_context"]["order"], ["wiki", "sources", "memory", "external"])
        excerpt = snapshot["external_verification"]["providers"][0]["evidence"][0]["excerpt"]
        self.assertLessEqual(len(excerpt), 400)
        self.assertTrue(excerpt.endswith("..."))

        memo_path = Path(result["idea_path"])
        self.assertTrue(memo_path.exists())
        frontmatter = _read_frontmatter(memo_path)
        self.assertEqual(frontmatter["idea_state"], "durable")
        self.assertTrue(frontmatter["verified"])
        self.assertEqual(frontmatter["verification_state"], "verified")
        self.assertIn("Paper Distill/insights/verification/", frontmatter["verification_snapshot"])

        mutation = get_mutation_record(self.tmp, result["mutation_id"])
        self.assertEqual(mutation["status"], "done")
        self.assertTrue(mutation["result"]["promoted"])

    def test_provider_failure_persists_snapshot_and_keeps_draft(self) -> None:
        result = verify_idea(
            self.tmp,
            idea=self._idea_payload(),
            verification={
                "required_providers": ["web-search", "papers-with-code"],
                "providers": [
                    {
                        "provider": "web-search",
                        "status": "failed",
                        "query": "active labeling manipulation long horizon failure analysis",
                        "error": "timeout",
                    },
                    {
                        "provider": "papers-with-code",
                        "status": "succeeded",
                        "query": "rare failure relabeling robotics",
                        "evidence": [
                            {
                                "title": "Benchmark gaps in long-horizon recovery",
                                "url": "https://example.com/benchmark-gaps",
                                "stance": "supporting",
                                "excerpt": "Some support exists, but one provider timed out.",
                            }
                        ],
                    },
                ],
            },
        )

        self.assertTrue(result["ok"])
        self.assertTrue(result["snapshot_persisted"])
        self.assertFalse(result["promoted"])
        self.assertEqual(result["idea_state"], "draft")
        self.assertEqual(result["verification_state"], "provider_failed")
        self.assertEqual(result["promotion_block_reason"], "provider_failed")

        memo_path = Path(result["idea_path"])
        frontmatter = _read_frontmatter(memo_path)
        self.assertEqual(frontmatter["idea_state"], "draft")
        self.assertEqual(frontmatter["providers_failed"], ["web-search"])

    def test_partial_verification_missing_provider_keeps_draft(self) -> None:
        result = verify_idea(
            self.tmp,
            idea=self._idea_payload(),
            verification={
                "required_providers": ["web-search", "semantic-scholar"],
                "providers": [
                    {
                        "provider": "web-search",
                        "status": "succeeded",
                        "query": "active labeling manipulation long horizon failure analysis",
                        "evidence": [
                            {
                                "title": "Failure-aware data selection for robotics",
                                "url": "https://example.com/failure-aware-data-selection",
                                "stance": "supporting",
                                "excerpt": "One provider succeeded, but the second provider is still missing.",
                            }
                        ],
                    }
                ],
            },
        )

        self.assertTrue(result["ok"])
        self.assertFalse(result["promoted"])
        self.assertEqual(result["idea_state"], "draft")
        self.assertEqual(result["verification_state"], "partial")
        self.assertEqual(result["missing_providers"], ["semantic-scholar"])
        self.assertEqual(result["promotion_block_reason"], "partial_evidence")

        snapshot = json.loads(Path(result["snapshot_path"]).read_text(encoding="utf-8"))
        self.assertEqual(snapshot["external_verification"]["missing_providers"], ["semantic-scholar"])

    def test_snapshot_is_persisted_before_draft_memo_write(self) -> None:
        observed: dict[str, object] = {}

        def _guarded_write(path: Path, frontmatter: dict, body: str) -> None:
            snapshots = sorted(root_path(self.tmp, "verification").rglob("*.json"))
            self.assertEqual(len(snapshots), 1)
            observed["snapshot_path"] = str(snapshots[0])
            observed["snapshot"] = json.loads(snapshots[0].read_text(encoding="utf-8"))
            observed["frontmatter"] = dict(frontmatter)
            observed["body"] = body
            vault_write_markdown(path, frontmatter, body)

        with patch("server.idea_verification.write_markdown", side_effect=_guarded_write):
            result = verify_idea(
                self.tmp,
                idea=self._idea_payload(),
                verification={
                    "required_providers": ["web-search", "semantic-scholar"],
                    "providers": [
                        {
                            "provider": "web-search",
                            "status": "succeeded",
                            "query": "active labeling manipulation long horizon failure analysis",
                            "evidence": [
                                {
                                    "title": "Failure-aware data selection for robotics",
                                    "url": "https://example.com/failure-aware-data-selection",
                                    "stance": "supporting",
                                    "excerpt": "One provider succeeded, but the second provider is still missing.",
                                }
                            ],
                        }
                    ],
                },
            )

        self.assertTrue(result["ok"])
        self.assertTrue(result["snapshot_persisted"])
        self.assertFalse(result["promoted"])
        self.assertEqual(result["idea_state"], "draft")
        self.assertEqual(result["promotion_block_reason"], "partial_evidence")
        self.assertEqual(observed["snapshot_path"], result["snapshot_path"])
        self.assertEqual(observed["snapshot"]["verification_state"], "partial")
        self.assertFalse(observed["snapshot"]["promotion_eligible"])
        self.assertEqual(observed["frontmatter"]["idea_state"], "draft")
        self.assertFalse(observed["frontmatter"]["verified"])
        self.assertEqual(
            observed["frontmatter"]["promotion_block_reason"],
            "partial_evidence",
        )
        self.assertIn("Verification state: partial", observed["body"])

    def test_contradiction_persists_snapshot_and_blocks_promotion(self) -> None:
        result = verify_idea(
            self.tmp,
            idea=self._idea_payload(),
            verification={
                "required_providers": ["web-search"],
                "providers": [
                    {
                        "provider": "web-search",
                        "status": "succeeded",
                        "query": "active labeling manipulation long horizon failure analysis",
                        "evidence": [
                            {
                                "title": "Failure-aware data selection for robotics",
                                "url": "https://example.com/failure-aware-data-selection",
                                "stance": "supporting",
                                "excerpt": "The provider found adjacent work.",
                            }
                        ],
                    }
                ],
                "contradictions": [
                    {
                        "ref": "Paper Distill/wiki/topics/manipulation.md",
                        "summary": "Local wiki already records a near-identical idea as infeasible under current sensing assumptions.",
                    }
                ],
            },
        )

        self.assertTrue(result["ok"])
        self.assertTrue(result["snapshot_persisted"])
        self.assertFalse(result["promoted"])
        self.assertEqual(result["idea_state"], "draft")
        self.assertEqual(result["verification_state"], "contradicted")
        self.assertEqual(result["promotion_block_reason"], "contradiction_detected")

        snapshot = json.loads(Path(result["snapshot_path"]).read_text(encoding="utf-8"))
        self.assertEqual(snapshot["verification_state"], "contradicted")
        self.assertEqual(len(snapshot["external_verification"]["contradictions"]), 1)

    def test_snapshot_write_failure_fails_loudly_and_does_not_write_memo(self) -> None:
        with patch("server.idea_verification._atomic_write_json", side_effect=OSError("disk full")):
            result = verify_idea(
                self.tmp,
                idea=self._idea_payload(),
                verification={
                    "required_providers": ["web-search"],
                    "providers": [
                        {
                            "provider": "web-search",
                            "status": "succeeded",
                            "query": "active labeling manipulation long horizon failure analysis",
                            "evidence": [
                                {
                                    "title": "Failure-aware data selection for robotics",
                                    "url": "https://example.com/failure-aware-data-selection",
                                    "stance": "supporting",
                                    "excerpt": "The provider found adjacent work.",
                                }
                            ],
                        }
                    ],
                },
            )

        self.assertFalse(result["ok"])
        self.assertFalse(result["snapshot_persisted"])
        self.assertFalse(result["promoted"])
        self.assertEqual(result["idea_write_state"], "failed")
        self.assertEqual(result["snapshot_write_state"], "failed")
        self.assertIn("disk full", result["error"])

        memo_path = root_path(self.tmp, "ideas") / "embodied-active-labeling.md"
        self.assertFalse(memo_path.exists())

        mutation = get_mutation_record(self.tmp, result["mutation_id"])
        self.assertEqual(mutation["status"], "failed")
        self.assertIn("disk full", mutation["error"])


if __name__ == "__main__":
    unittest.main()
