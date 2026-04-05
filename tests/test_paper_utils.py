from __future__ import annotations

import unittest

from server.paper_utils import canonical_html_url, canonical_pdf_url, normalize_venue_tier, paper_id


class PaperUtilsTest(unittest.TestCase):
    def test_canonical_arxiv_urls_prefer_arxiv_assets(self) -> None:
        paper = {
            "doi": "10.48550/arxiv.2501.00001",
        }
        self.assertEqual(canonical_pdf_url(paper), "https://arxiv.org/pdf/2501.00001.pdf")
        self.assertEqual(canonical_html_url(paper), "https://ar5iv.labs.arxiv.org/html/2501.00001")

    def test_paper_id_prefers_doi(self) -> None:
        value = paper_id(
            {
                "title": "Vision Language Action",
                "authors": ["Jane Doe"],
                "year": 2025,
                "doi": "10.48550/arxiv.2501.00001",
            }
        )
        self.assertEqual(value, "doi:10.48550/arxiv.2501.00001")

    def test_paper_id_falls_back_to_arxiv(self) -> None:
        value = paper_id(
            {
                "title": "Vision Language Action",
                "authors": ["Jane Doe"],
                "year": 2025,
                "open_access_url": "https://arxiv.org/abs/2501.00001",
            }
        )
        self.assertEqual(value, "arxiv:2501.00001")

    def test_normalize_venue_tier_handles_alias_and_workshop(self) -> None:
        aliases = {"nips": "NeurIPS"}
        tiers = {"tier_s": ["NeurIPS"], "tier_a": []}

        normalized, tier = normalize_venue_tier("NIPS 2025", aliases, tiers)
        self.assertEqual(normalized, "NeurIPS")
        self.assertEqual(tier, "tier_s")

        _, workshop_tier = normalize_venue_tier("CVPR Workshop on Agents", aliases, tiers)
        self.assertEqual(workshop_tier, "workshop_or_unclear")
