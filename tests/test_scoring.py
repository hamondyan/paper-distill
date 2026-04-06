from __future__ import annotations

import asyncio
import unittest
from unittest.mock import AsyncMock, patch

from server.server import _enrich_inbox_candidate, _selected_topics, discover_papers, score_papers


class ScoringTest(unittest.TestCase):
    def test_selected_topics_falls_back_to_ad_hoc_topic_keys(self) -> None:
        with patch("server.server.get_topics", return_value={}):
            selected = _selected_topics(None, ["vision-language-action", "manipulation"])

        self.assertEqual(sorted(selected.keys()), ["manipulation", "vision-language-action"])
        self.assertEqual(selected["manipulation"]["keywords"], ["manipulation"])

    def test_top_tier_venue_is_visible_in_breakdown(self) -> None:
        papers = [
            {
                "title": "Vision Language Action Policies",
                "abstract": "A vision language action model for robot control.",
                "authors": ["Jane Doe"],
                "year": 2025,
                "venue": "NeurIPS 2025",
                "citation_count": None,
            },
            {
                "title": "Vision Language Action Policies Workshop",
                "abstract": "A workshop version of the same topic.",
                "authors": ["Jane Doe"],
                "year": 2025,
                "venue": "NeurIPS Workshop 2025",
                "citation_count": None,
            },
        ]

        scored = asyncio.run(
            score_papers(
                papers=papers,
                topics={
                    "vision-language-action": {
                        "label": "Vision-Language-Action",
                        "keywords": ["VLA", "vision language action"],
                    }
                },
                known_ids=[],
                whitelist_authors=[],
                preferred_venues=[],
                venue_aliases={"nips": "NeurIPS"},
                venue_tiers={"tier_s": ["NeurIPS"], "tier_a": []},
            )
        )

        self.assertEqual(scored[0]["venue_tier"], "tier_s")
        self.assertGreater(
            scored[0]["_score_breakdown"]["venue_tier"],
            scored[1]["_score_breakdown"]["venue_tier"],
        )

    def test_best_topic_wins_without_multi_topic_dilution(self) -> None:
        papers = [
            {
                "title": "Vision Language Action Policies",
                "abstract": "A strong VLA paper.",
                "authors": ["Jane Doe"],
                "year": 2025,
                "venue": "CVPR",
                "citation_count": None,
            }
        ]
        scored = asyncio.run(
            score_papers(
                papers=papers,
                topics={
                    "vision-language-action": {
                        "label": "Vision-Language-Action",
                        "keywords": ["VLA", "vision language action"],
                    },
                    "manipulation": {
                        "label": "Manipulation",
                        "keywords": ["manipulation"],
                    },
                },
                known_ids=[],
                whitelist_authors=[],
                preferred_venues=[],
                venue_tiers={"tier_s": ["CVPR"], "tier_a": []},
            )
        )
        self.assertEqual(scored[0]["best_topic"], "vision-language-action")
        self.assertGreater(scored[0]["_score_breakdown"]["topic_fit"], 0.0)

    def test_discover_merges_matched_topics_for_same_paper(self) -> None:
        paper = {
            "title": "Vision Language Action Manipulation Policies",
            "abstract": "A VLA system for robot manipulation.",
            "authors": ["Jane Doe"],
            "year": 2025,
            "venue": "CVPR",
            "doi": "10.1000/example",
            "citation_count": None,
            "source": "openalex",
        }

        with patch("server.server.search_papers", new=AsyncMock(return_value=[paper])):
            with patch("server.server._existing_paper_ids", return_value=set()):
                with patch(
                    "server.server.bind_paper_to_arxiv",
                    new=AsyncMock(
                        side_effect=lambda value: {
                            **value,
                            "arxiv_id": "2501.00001",
                            "paper_id": "doi:10.1000/example",
                            "canonical_html_url": "https://ar5iv.labs.arxiv.org/html/2501.00001",
                            "canonical_pdf_url": "https://arxiv.org/pdf/2501.00001.pdf",
                            "canonical_item_url": "https://ar5iv.labs.arxiv.org/html/2501.00001",
                            "arxiv_binding_status": "matched",
                        }
                    )
                ):
                    discovered = asyncio.run(
                        discover_papers(
                            topic_keys=["vision-language-action", "manipulation"],
                            save_to_inbox=False,
                        )
                    )

        self.assertEqual(len(discovered["papers"]), 1)
        self.assertEqual(
            discovered["papers"][0]["matched_topics"],
            ["manipulation", "vision-language-action"],
        )

    def test_enrich_inbox_candidate_preserves_configured_venue_tier(self) -> None:
        enriched = asyncio.run(
            _enrich_inbox_candidate(
                {
                    "title": "A VLA Paper",
                    "authors": ["Jane Doe"],
                    "year": 2025,
                    "venue_raw": "IROS",
                }
            )
        )
        self.assertEqual(enriched["venue_normalized"], "IROS")
        self.assertEqual(enriched["venue_tier"], "tier_s")
