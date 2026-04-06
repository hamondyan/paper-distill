from __future__ import annotations

import unittest

from server.arxiv_section_filters import filter_section_titles, normalize_section_title, should_keep_section


class ArxivSectionFiltersTest(unittest.TestCase):
    def test_normalize_section_title_strips_numbering(self) -> None:
        self.assertEqual(normalize_section_title("1 Introduction"), "introduction")
        self.assertEqual(normalize_section_title("A.1 Appendix"), "appendix")
        self.assertEqual(normalize_section_title("III Related Work"), "related work")

    def test_should_keep_section_supports_exclude(self) -> None:
        self.assertFalse(should_keep_section("References", mode="exclude", selected=["references"]))
        self.assertTrue(should_keep_section("Method", mode="exclude", selected=["references"]))

    def test_filter_section_titles_keeps_selected_titles_in_include_mode(self) -> None:
        self.assertEqual(
            filter_section_titles(["1 Introduction", "2 Method", "References"], mode="include", selected=["method"]),
            ["2 Method"],
        )
