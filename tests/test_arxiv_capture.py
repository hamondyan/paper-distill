from __future__ import annotations

import asyncio
import unittest
from unittest.mock import AsyncMock, patch

from server.arxiv_capture import bind_paper_to_arxiv, build_crgp_dnl, clean_ar5iv_html


_SAMPLE_AR5IV_HTML = """
<html>
  <body>
    <article class="ltx_document">
      <h1 class="ltx_title ltx_title_document">A Structured VLA Paper</h1>
      <div class="ltx_abstract">
        <h6 class="ltx_title ltx_title_abstract">Abstract</h6>
        <p class="ltx_p">We present a vision-language-action system for long-horizon manipulation. The method improves token efficiency and stabilizes parallel decoding at inference time.</p>
      </div>
      <section class="ltx_section">
        <h2 class="ltx_title ltx_title_section">1 Introduction</h2>
        <div class="ltx_para"><p class="ltx_p">Prior VLA systems struggle with long-horizon action planning and however become brittle when action tokens are too small. This challenge matters for robotic manipulation because compounding errors quickly dominate multi-step tasks.</p></div>
        <div class="ltx_para"><p class="ltx_p">We study a source-backed pipeline that keeps arXiv captures stable enough for knowledge compilation, and we emphasize reliable section extraction for downstream note generation.</p></div>
      </section>
      <section class="ltx_section">
        <h2 class="ltx_title ltx_title_section">2 Method</h2>
        <div class="ltx_para"><p class="ltx_p">Our proposal scales the action tokenizer, introduces a hierarchical control stack, and combines the policy with parallel decoding to reduce rollout latency while preserving semantic grounding.</p></div>
        <figure><figcaption class="ltx_caption">Figure 1: The method uses token scaling and parallel decoding.</figcaption></figure>
      </section>
      <section class="ltx_section">
        <h2 class="ltx_title ltx_title_section">3 Evaluation</h2>
        <div class="ltx_para"><p class="ltx_p">Experiments show stronger success rates on manipulation benchmarks and more stable long-horizon control. The evaluation also highlights improved throughput under parallel decoding.</p></div>
      </section>
      <section class="ltx_section">
        <h2 class="ltx_title ltx_title_section">4 Discussion</h2>
        <div class="ltx_para"><p class="ltx_p">A remaining limitation is sensitivity to synthetic action distribution shift, and future work should stress-test transfer beyond the observed benchmark suite.</p></div>
      </section>
      <section class="ltx_section">
        <h2 class="ltx_title ltx_title_section">Appendix A Additional Details</h2>
        <div class="ltx_para"><p class="ltx_p">The appendix adds ablations for tokenizer size and provides extra rollout traces for failure analysis.</p></div>
        <div class="ltx_para"><p class="ltx_p">A second appendix paragraph should not fully survive the summary-only policy.</p></div>
      </section>
      <section id="bib" class="ltx_bibliography">
        <h2 class="ltx_title ltx_title_bibliography">References</h2>
        <p class="ltx_p">[1] Example reference that should be removed.</p>
      </section>
    </article>
  </body>
</html>
"""


class ArxivCaptureTest(unittest.TestCase):
    def test_bind_paper_to_arxiv_rejects_author_mismatch(self) -> None:
        paper = {
            "title": "A Structured VLA Paper",
            "authors": ["Jane Doe"],
            "year": 2025,
        }
        matches = [
            {
                "title": "A Structured VLA Paper",
                "authors": ["Alex Smith"],
                "year": 2025,
                "arxiv_id": "2501.00001",
            }
        ]

        with patch("server.arxiv_capture.search_arxiv_title_author", new=AsyncMock(return_value=matches)):
            bound = asyncio.run(bind_paper_to_arxiv(paper))

        self.assertIsNone(bound)

    def test_clean_ar5iv_html_keeps_sections_and_summarizes_appendix(self) -> None:
        cleaned = clean_ar5iv_html(_SAMPLE_AR5IV_HTML, min_body_chars=300)

        self.assertEqual(cleaned.title, "A Structured VLA Paper")
        self.assertIn("## Abstract", cleaned.markdown)
        self.assertIn("## Appendix Snapshot", cleaned.markdown)
        self.assertIn("Figure 1: The method uses token scaling and parallel decoding.", cleaned.markdown)
        self.assertNotIn("Example reference that should be removed", cleaned.markdown)
        self.assertEqual(cleaned.appendix_snapshot[0]["heading"], "Appendix A Additional Details")
        self.assertNotIn("second appendix paragraph", cleaned.markdown)

    def test_build_crgp_dnl_uses_cleaned_sections(self) -> None:
        cleaned = clean_ar5iv_html(_SAMPLE_AR5IV_HTML, min_body_chars=300)
        note = build_crgp_dnl(
            {
                "title": cleaned.title,
                "authors": ["Jane Doe"],
                "year": 2025,
                "arxiv_id": "2501.00001",
            },
            cleaned,
        )

        self.assertIn("parallel decoding", note["sections"]["Proposal"].lower())
        self.assertIn("benchmark", note["sections"]["Key Results"].lower())
        self.assertGreaterEqual(note["confidence"], 0.7)

