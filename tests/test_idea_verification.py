from __future__ import annotations

import shutil
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import yaml

from server.database import close_db
from server.idea_verification import verify_idea
from server.vault_ops import ensure_vault_structure


def _split_note(path: Path) -> tuple[dict, str]:
    content = path.read_text(encoding="utf-8")
    _, remainder = content.split("---\n", 1)
    fm_text, body = remainder.split("\n---\n", 1)
    return yaml.safe_load(fm_text) or {}, body.strip()


class IdeaVerificationNoteTest(unittest.TestCase):
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
                        "ref": "Paper Distill/sources/evidence/2026-04-08/fixture.md",
                        "summary": "Source evidence highlights rare recovery failures after occlusion.",
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

    def _assert_no_secondary_artifacts(self) -> None:
        verification_files = list(
            (Path(self.tmp) / "Paper Distill" / "insights" / "verification").rglob("*.json")
        )
        self.assertEqual(verification_files, [])

    def test_verified_idea_writes_single_active_note(self) -> None:
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
        self.assertEqual(result["idea_state"], "active")
        self.assertEqual(result["verification_state"], "verified")
        self.assertEqual(result["decision_reason"], "")
        self.assertEqual(result["decision_at"], "")
        self.assertEqual(result["idea_write_state"], "saved")

        note_path = Path(result["idea_path"])
        self.assertTrue(note_path.exists())
        frontmatter, body = _split_note(note_path)
        self.assertEqual(frontmatter["type"], "idea-note")
        self.assertEqual(frontmatter["idea_state"], "active")
        self.assertEqual(frontmatter["verification_state"], "verified")
        self.assertEqual(frontmatter["decision_reason"], "")
        self.assertEqual(frontmatter["decision_at"], "")
        self.assertEqual(frontmatter["status"], "saved")
        self.assertEqual(frontmatter["providers_succeeded"], ["web-search", "papers-with-code"])
        self.assertNotIn("verification_snapshot", frontmatter)
        self.assertIn("## Summary", body)
        self.assertIn("## Local Evidence", body)
        self.assertIn("## Hypothesis / Bridge", body)
        self.assertIn("## Kill Criteria", body)
        self.assertIn("## Next Step", body)
        self.assertIn("### External Checks", body)
        self._assert_no_secondary_artifacts()

    def test_provider_failure_marks_note_parked_without_memory_followup(self) -> None:
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
        self.assertEqual(result["idea_state"], "parked")
        self.assertEqual(result["verification_state"], "provider_failed")
        self.assertEqual(result["decision_reason"], "provider_failed")
        self.assertTrue(result["decision_at"])
        self.assertEqual(result["missing_providers"], [])

        frontmatter, body = _split_note(Path(result["idea_path"]))
        self.assertEqual(frontmatter["idea_state"], "parked")
        self.assertEqual(frontmatter["decision_reason"], "provider_failed")
        self.assertEqual(frontmatter["providers_failed"], ["web-search"])
        self.assertIn("web-search", body)
        self.assertIn("papers-with-code", body)
        self.assertIn("Collect a clean pass from the failed or missing providers", body)
        self._assert_no_secondary_artifacts()

    def test_partial_verification_marks_note_parked_with_missing_provider(self) -> None:
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
        self.assertEqual(result["idea_state"], "parked")
        self.assertEqual(result["verification_state"], "partial")
        self.assertEqual(result["decision_reason"], "partial_evidence")
        self.assertEqual(result["missing_providers"], ["semantic-scholar"])

        frontmatter, body = _split_note(Path(result["idea_path"]))
        self.assertEqual(frontmatter["idea_state"], "parked")
        self.assertEqual(frontmatter["missing_providers"], ["semantic-scholar"])
        self.assertIn("semantic-scholar", body)
        self.assertIn("missing providers complete their checks", body)
        self._assert_no_secondary_artifacts()

    def test_contradiction_marks_note_rejected_and_keeps_reason_in_note(self) -> None:
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
        self.assertEqual(result["idea_state"], "rejected")
        self.assertEqual(result["verification_state"], "contradicted")
        self.assertEqual(result["decision_reason"], "contradiction_detected")
        self.assertTrue(result["decision_at"])

        frontmatter, body = _split_note(Path(result["idea_path"]))
        self.assertEqual(frontmatter["idea_state"], "rejected")
        self.assertEqual(frontmatter["decision_reason"], "contradiction_detected")
        self.assertIn("## Kill Criteria", body)
        self.assertIn("Local wiki already records a near-identical idea", body)
        self.assertIn("Only reopen if the contradiction is resolved", body)
        self._assert_no_secondary_artifacts()

    def test_note_write_failure_fails_without_creating_secondary_artifacts(self) -> None:
        with patch("server.idea_verification.write_markdown", side_effect=OSError("disk full")):
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
        self.assertEqual(result["idea_write_state"], "failed")
        self.assertEqual(result["idea_state"], "unchanged")
        self.assertIn("disk full", result["error"])
        self.assertFalse(
            (Path(self.tmp) / "Paper Distill" / "insights" / "ideas" / "embodied-active-labeling.md").exists()
        )
        self._assert_no_secondary_artifacts()


if __name__ == "__main__":
    unittest.main()
