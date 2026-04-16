from __future__ import annotations

import asyncio
import unittest
from unittest.mock import AsyncMock, patch

from server.arxiv_capture import bind_paper_to_arxiv, capture_arxiv_source, clean_ar5iv_html


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
        <div class="ltx_equation"><math alttext="a_t = \\pi(o_t, g_t)">a_t = π(o_t, g_t)</math></div>
        <figure><figcaption class="ltx_caption">Figure 1: The method uses token scaling and parallel decoding.</figcaption></figure>
      </section>
      <section class="ltx_section">
        <h2 class="ltx_title ltx_title_section">3 Evaluation</h2>
        <div class="ltx_para"><p class="ltx_p">Experiments show stronger success rates on manipulation benchmarks and more stable long-horizon control. The evaluation also highlights improved throughput under parallel decoding.</p></div>
        <figure class="ltx_table">
          <figcaption class="ltx_caption">Table 1: Success rate and throughput both improve.</figcaption>
          <table class="ltx_tabular">
            <tr><th>Model</th><th>Success</th><th>Throughput</th></tr>
            <tr><td>Baseline</td><td>61</td><td>1.0x</td></tr>
            <tr><td>Ours</td><td>78</td><td>1.8x</td></tr>
          </table>
        </figure>
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
        self.assertIn("## Captured Assets Index", cleaned.markdown)
        self.assertNotIn("## Figure Snapshot", cleaned.markdown)
        self.assertNotIn("## Table Snapshot", cleaned.markdown)
        self.assertNotIn("## Equation Snapshot", cleaned.markdown)
        self.assertIn("**Equation E1**", cleaned.markdown)
        self.assertIn("$$\na_t = \\pi(o_t, g_t)\n$$", cleaned.markdown)
        self.assertIn("**Figure 1**", cleaned.markdown)
        self.assertIn("Figure 1: The method uses token scaling and parallel decoding.", cleaned.markdown)
        self.assertIn("**Table 1**", cleaned.markdown)
        self.assertIn("| Model | Success | Throughput |", cleaned.markdown)
        self.assertIn("- Figures captured: 1", cleaned.markdown)
        self.assertIn("- Tables captured: 1", cleaned.markdown)
        self.assertIn("- Equations captured: 1", cleaned.markdown)
        self.assertEqual(cleaned.markdown.count("Table 1: Success rate and throughput both improve."), 1)
        self.assertLess(cleaned.markdown.index("## 2 Method"), cleaned.markdown.index("**Equation E1**"))
        self.assertLess(cleaned.markdown.index("**Equation E1**"), cleaned.markdown.index("**Figure 1**"))
        self.assertLess(cleaned.markdown.index("## 3 Evaluation"), cleaned.markdown.index("**Table 1**"))
        self.assertEqual(cleaned.quality["figure_count"], 1)
        self.assertEqual(cleaned.quality["table_count"], 1)
        self.assertEqual(cleaned.quality["equation_count"], 1)
        self.assertEqual(cleaned.capture_fidelity, "high")
        self.assertIn("a_t = \\pi(o_t, g_t)", cleaned.equations[0]["text"])
        self.assertNotIn("Example reference that should be removed", cleaned.markdown)
        self.assertEqual(cleaned.appendix_snapshot[0]["heading"], "Appendix A Additional Details")
        self.assertNotIn("second appendix paragraph", cleaned.markdown)

    def test_clean_ar5iv_html_supports_drop_appendix(self) -> None:
        cleaned = clean_ar5iv_html(_SAMPLE_AR5IV_HTML, appendix_policy="drop", min_body_chars=300)

        self.assertNotIn("## Appendix Snapshot", cleaned.markdown)
        self.assertEqual(cleaned.appendix_snapshot, [])

    def test_clean_ar5iv_html_can_remove_inline_citations(self) -> None:
        html = _SAMPLE_AR5IV_HTML.replace(
            "We study a source-backed pipeline that keeps arXiv captures stable enough for knowledge compilation, and we emphasize reliable section extraction for downstream note generation.",
            "We study a source-backed pipeline <cite class=\"ltx_cite ltx_citemacro_citep\">(Anthropic, <a class=\"ltx_ref\" href=\"#bib.bib4\">2024</a>)</cite> that keeps arXiv captures stable enough for knowledge compilation.",
        )

        cleaned = clean_ar5iv_html(html, min_body_chars=300, remove_inline_citations=True)

        self.assertNotIn("Anthropic", cleaned.markdown)

    def test_clean_ar5iv_html_can_preserve_internal_links_when_requested(self) -> None:
        html = _SAMPLE_AR5IV_HTML.replace(
            "We study a source-backed pipeline that keeps arXiv captures stable enough for knowledge compilation, and we emphasize reliable section extraction for downstream note generation.",
            "We study a source-backed pipeline and refer readers to <a class=\"ltx_ref\" href=\"https://arxiv.org/html/2501.00001#S2\">Section 2</a> for details on the method and evaluation coverage.",
        )

        cleaned = clean_ar5iv_html(html, min_body_chars=300, remove_internal_links=False)

        self.assertIn("[Section 2](https://arxiv.org/html/2501.00001#S2)", cleaned.markdown)

    def test_capture_arxiv_source_records_fetch_provenance(self) -> None:
        paper = {"doi": "10.48550/arxiv.2501.00001"}

        async def run() -> tuple[str, str]:
            with patch(
                "server.arxiv_capture.fetch_arxiv_html",
                new=AsyncMock(return_value=(_SAMPLE_AR5IV_HTML, "arxiv_native_html")),
            ):
                cleaned = await capture_arxiv_source(paper, min_body_chars=300)
            return cleaned.capture_source, cleaned.capture_method

        capture_source, capture_method = asyncio.run(run())

        self.assertEqual(capture_source, "arxiv_native_html")
        self.assertEqual(capture_method, "arxiv_native_html_cleaned")
