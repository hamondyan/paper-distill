from __future__ import annotations

import json
import os
import shutil
import tempfile
import unittest
from pathlib import Path

from server.database import close_db, get_db
from server.vault_lint import analyze_knowledge_graph_sync
from server.vault_ops import write_markdown


class TriggerCandidatesTest(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.mkdtemp()
        pd_root = os.path.join(self.tmp, "Paper Distill")
        for d in ["wiki/papers", "wiki/concepts", ".state", ".state/ir"]:
            os.makedirs(os.path.join(pd_root, d), exist_ok=True)
        get_db(self.tmp)

    def tearDown(self) -> None:
        close_db(self.tmp)
        shutil.rmtree(self.tmp)

    def _write_paper(self, citekey: str, topics: list[str], concepts: list[str]) -> None:
        write_markdown(
            Path(self.tmp) / "Paper Distill" / "wiki" / "papers" / f"{citekey}.md",
            {
                "citekey": citekey,
                "title": citekey,
                "topics": topics,
                "concepts": concepts,
                "limitations": ["sim-to-real gap"],
                "open_questions": ["How to transfer?"],
            },
            "\n".join(f"[[concepts/{c}]]" for c in concepts),
        )

    def _write_concept(self, concept: str, topics: list[str]) -> None:
        write_markdown(
            Path(self.tmp) / "Paper Distill" / "wiki" / "concepts" / f"{concept}.md",
            {"concept": concept, "topics": topics},
            f"# {concept}",
        )

    def _write_ir(
        self,
        citekey: str,
        *,
        limitation: str,
        benchmark_scope: str,
        novelty: str,
        negative_result: str,
    ) -> None:
        payload = {
            "citekey": citekey,
            "_resolved": True,
            "_resolutions": [],
            "benchmark_scope": benchmark_scope,
            "claimed_novelty": novelty,
            "tension_fields": {
                "limitations": [{"claim": limitation, "source_ref": f"sources/evidence/{citekey}/section-6"}],
                "assumptions": [{"claim": "Requires dense data", "source_ref": f"sources/evidence/{citekey}/section-2"}],
                "failure_modes": [{"claim": "Fails under occlusion", "source_ref": f"sources/evidence/{citekey}/table-4"}],
                "transfer_constraints": [{"claim": "No real robot eval", "source_ref": f"sources/evidence/{citekey}/section-7"}],
                "open_questions": [{"question": "How to scale to real robots?", "source_ref": f"sources/evidence/{citekey}/section-8"}],
                "negative_results": [{"claim": negative_result, "source_ref": f"sources/evidence/{citekey}/table-5"}],
            },
        }
        with open(os.path.join(self.tmp, "Paper Distill", ".state", "ir", f"{citekey}_resolved.json"), "w", encoding="utf-8") as f:
            json.dump(payload, f)

    def test_trigger_candidates_surface_from_graph_and_ir(self) -> None:
        self._write_concept("concept-a", ["robotics"])
        self._write_concept("concept-b", ["robotics"])

        self._write_paper("paper1", ["robotics"], ["concept-a"])
        self._write_paper("paper2", ["robotics"], ["concept-b"])
        self._write_paper("paper3", ["robotics"], ["concept-a", "concept-b"])

        self._write_ir(
            "paper1",
            limitation="sim-to-real gap remains severe",
            benchmark_scope="simulation only",
            novelty="novel attention policy improves occlusion robustness",
            negative_result="novel attention degrades under severe occlusion",
        )
        self._write_ir(
            "paper2",
            limitation="sim-to-real gap remains severe",
            benchmark_scope="real robot evaluation",
            novelty="novel attention policy improves long-horizon alignment",
            negative_result="novel attention degrades under severe occlusion",
        )
        self._write_ir(
            "paper3",
            limitation="sim-to-real gap remains severe",
            benchmark_scope="simulation only",
            novelty="novel attention bridge model",
            negative_result="novel attention degrades under severe occlusion",
        )

        result = analyze_knowledge_graph_sync(self.tmp, user_topics=["robotics"])
        gaps = result["gaps"]

        self.assertGreater(len(gaps.get("cross_cluster_bridges", [])), 0)
        self.assertGreater(len(gaps.get("benchmark_evaluation_splits", [])), 0)
        self.assertGreater(len(gaps.get("recurring_limitation_spikes", [])), 0)
        self.assertGreater(len(gaps.get("contradiction_candidates", [])), 0)
