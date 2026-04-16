from __future__ import annotations

import asyncio

from server.v3_scoring import score_papers_v3


def test_score_papers_v3_prefers_the_best_topic() -> None:
    papers = [
        {
            "title": "Vision Language Action Policies",
            "abstract": "A strong VLA paper for robot control.",
            "authors": ["Jane Doe"],
            "year": 2025,
            "venue": "CVPR",
            "citation_count": None,
        }
    ]

    scored = asyncio.run(
        score_papers_v3(
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

    assert scored[0]["best_topic"] == "vision-language-action"
    assert scored[0]["_score_breakdown"]["topic_fit"] > 0.0


def test_score_papers_v3_keeps_venue_tier_visible_in_breakdown() -> None:
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
        score_papers_v3(
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

    assert scored[0]["venue_tier"] == "tier_s"
    assert scored[0]["_score_breakdown"]["venue_tier"] > scored[1]["_score_breakdown"]["venue_tier"]


def test_score_papers_v3_applies_rejected_keyword_penalties() -> None:
    papers = [
        {
            "title": "Efficient Vision Transformers for Robotics",
            "abstract": "Unlike medical imaging approaches, we focus on robot control.",
            "authors": ["Bob"],
            "year": 2025,
        }
    ]

    scored = asyncio.run(
        score_papers_v3(
            papers=papers,
            topics={"robotics": {"label": "Robotics", "keywords": ["robotics"]}},
            known_ids=[],
            whitelist_authors=[],
            preferred_venues=[],
            runtime_context={
                "effective_preferences": {
                    "rejected_keywords": ["medical"],
                }
            },
        )
    )

    assert scored[0]["_score_breakdown"]["rejected_penalty"] == -0.4
