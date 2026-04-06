from __future__ import annotations

import unittest

from server.arxiv_markdown import convert_fragment_to_markdown


class ArxivMarkdownTest(unittest.TestCase):
    def test_convert_fragment_renders_math_and_figure_wrapped_table(self) -> None:
        html = """
        <div><p>Equation <math><annotation encoding="application/x-tex">x+y</annotation></math></p></div>
        <figure class="ltx_table">
          <table class="ltx_tabular">
            <thead><tr><th>A</th><th>B</th></tr></thead>
            <tbody><tr><td>1</td><td>2</td></tr></tbody>
          </table>
          <figcaption>Table 1: Example.</figcaption>
        </figure>
        """

        markdown = convert_fragment_to_markdown(html)

        self.assertIn("$x+y$", markdown)
        self.assertIn("Table 1: Example.", markdown)
        self.assertIn("| A | B |", markdown)
        self.assertIn("| 1 | 2 |", markdown)

    def test_convert_fragment_can_remove_inline_citations(self) -> None:
        html = """
        <p>We study
        <cite class="ltx_cite ltx_citemacro_citep">(Anthropic, <a class="ltx_ref" href="#bib.bib4">2024</a>)</cite>
        systems.</p>
        """

        markdown = convert_fragment_to_markdown(html, remove_inline_citations=True)

        self.assertIn("We study", markdown)
        self.assertIn("systems.", markdown)
        self.assertNotIn("Anthropic", markdown)
