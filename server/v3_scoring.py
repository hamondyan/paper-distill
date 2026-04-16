from __future__ import annotations

import asyncio
import logging
from typing import Any

from server.config import get_paper_distill_settings, get_scoring_settings, get_topics
from server.paper_scoring import (
    _annotate_paper,
    _best_topic_fit,
    _canonical_topics,
    _score_author_preference,
    _score_impact,
    _score_metadata_quality,
    _score_novelty,
    _score_recency,
    _score_venue_tier,
)
from server.search import (
    dedup_merge,
    search_arxiv,
    search_dblp,
    search_openalex,
    search_papers_with_code,
    search_semantic_scholar,
)

LOG = logging.getLogger(__name__)

_SEARCH_SOURCES = {
    "arxiv": search_arxiv,
    "s2": search_semantic_scholar,
    "openalex": search_openalex,
    "dblp": search_dblp,
    "pwc": search_papers_with_code,
}
_SOURCE_TIMEOUT = 15


def _score_keyword_alignment(paper: dict[str, Any], keywords: list[str] | None) -> float:
    if not keywords:
        return 0.0

    normalized_keywords: list[str] = []
    seen_keywords: set[str] = set()
    for keyword in keywords:
        normalized = str(keyword or "").strip().lower()
        if len(normalized) < 3 or normalized in seen_keywords:
            continue
        seen_keywords.add(normalized)
        normalized_keywords.append(normalized)
    if not normalized_keywords:
        return 0.0

    title = (paper.get("title") or "").lower()
    abstract = (paper.get("abstract") or "").lower()
    venue = (paper.get("venue_normalized") or paper.get("venue") or "").lower()

    matched_score = 0.0
    for normalized in normalized_keywords:
        if normalized in title:
            matched_score += 0.45
        elif normalized in abstract:
            matched_score += 0.20
        elif normalized in venue:
            matched_score += 0.10

    max_score = max(len(normalized_keywords) * 0.45, 0.45)
    return min(matched_score / max_score, 1.0)


def _score_rejected_keywords(
    paper: dict[str, Any],
    rejected_keywords: list[str] | None,
) -> float:
    if not rejected_keywords:
        return 0.0

    rejected_lower = [kw.strip().lower() for kw in rejected_keywords if kw.strip()]
    if not rejected_lower:
        return 0.0

    title = (paper.get("title") or "").lower()
    abstract = (paper.get("abstract") or "").lower()
    venue = (paper.get("venue_normalized") or paper.get("venue") or "").lower()

    worst = 0.0
    for keyword in rejected_lower:
        if keyword in title:
            worst = min(worst, -0.80)
        elif keyword in abstract:
            worst = min(worst, -0.40)
        elif keyword in venue:
            worst = min(worst, -0.15)
    return worst


async def _search_with_timeout(fn, query: str, max_results: int, name: str):
    try:
        return await asyncio.wait_for(fn(query, max_results=max_results), _SOURCE_TIMEOUT)
    except asyncio.TimeoutError:
        LOG.warning("Search %s timed out after %ds", name, _SOURCE_TIMEOUT)
        return []
    except Exception as exc:  # pragma: no cover - defensive path
        LOG.warning("Search %s failed: %s", name, exc)
        return []


async def search_papers_v3(
    query: str,
    sources: list[str] | None = None,
    max_results: int = 20,
) -> list[dict[str, Any]]:
    if sources is None:
        sources = list(_SEARCH_SOURCES.keys())

    tasks = []
    source_names = []
    for source in sources:
        fn = _SEARCH_SOURCES.get(source)
        if fn is None:
            continue
        tasks.append(_search_with_timeout(fn, query, max_results, source))
        source_names.append(source)

    if not tasks:
        return []

    results = await asyncio.gather(*tasks)
    all_papers: list[dict[str, Any]] = []
    for name, batch in zip(source_names, results):
        if batch:
            LOG.info("Search %s: %d results", name, len(batch))
            all_papers.extend(batch)
        else:
            LOG.info("Search %s: 0 results", name)

    settings = get_paper_distill_settings()
    scoring_settings = get_scoring_settings()
    authority_order = settings.get("venue", {}).get("authority_order", [])
    merged = [
        _annotate_paper(
            paper,
            venue_aliases=scoring_settings.get("venue_aliases", {}),
            venue_tiers=scoring_settings.get("venue_tiers", {}),
        )
        for paper in dedup_merge(all_papers, authority_order=authority_order)
    ]
    LOG.info(
        "Total: %d papers after dedup (from %d candidates)",
        len(merged),
        len(all_papers),
    )
    return merged


async def score_papers_v3(
    papers: list[dict[str, Any]],
    topic_keywords: list[str] | None = None,
    known_dois: list[str] | None = None,
    topics: dict | None = None,
    known_ids: list[str] | None = None,
    whitelist_authors: list[str] | None = None,
    preferred_venues: list[str] | None = None,
    venue_aliases: dict | None = None,
    venue_tiers: dict | None = None,
    runtime_context: dict | None = None,
) -> list[dict[str, Any]]:
    settings = get_paper_distill_settings()
    scoring_settings = settings.get("scoring", {})
    weights = scoring_settings.get("weights", {})
    topics_map = _canonical_topics(topics=topics, topic_keywords=topic_keywords)

    if not topics_map:
        topics_map = _canonical_topics(topics=get_topics())

    aliases = venue_aliases or scoring_settings.get("venue_aliases", {})
    tiers = venue_tiers or scoring_settings.get("venue_tiers", {})
    effective_preferences = (
        dict(runtime_context.get("effective_preferences") or {})
        if isinstance(runtime_context, dict)
        else {}
    )
    settings_preferences = settings.get("research_profile", {}).get("learned_preferences", {})
    preferred_venues = (
        preferred_venues
        or effective_preferences.get("preferred_venues")
        or settings_preferences.get("preferred_venues", [])
    )
    whitelist_authors = (
        whitelist_authors
        or effective_preferences.get("whitelist_authors")
        or settings.get("research_profile", {}).get("whitelist_authors", [])
    )
    rejected_keywords = effective_preferences.get("rejected_keywords") or settings_preferences.get(
        "rejected_keywords",
        [],
    )
    profile_terms = effective_preferences.get("profile_terms") or []
    taste_terms = effective_preferences.get("taste_terms") or []

    known_id_set = {item.strip().lower() for item in (known_ids or []) if item}
    known_id_set.update(
        f"doi:{doi.strip().lower()}" for doi in (known_dois or []) if doi
    )

    scored: list[dict[str, Any]] = []
    for paper in papers:
        annotated = _annotate_paper(paper, venue_aliases=aliases, venue_tiers=tiers)
        best_topic, topic_fit = _best_topic_fit(annotated, topics_map)
        recency = _score_recency(annotated)
        novelty = _score_novelty(annotated, known_id_set)
        impact = _score_impact(annotated)
        venue_score = _score_venue_tier(annotated)
        author_pref = _score_author_preference(
            annotated,
            whitelist_authors=whitelist_authors,
            preferred_venues=preferred_venues,
        )
        metadata_quality = _score_metadata_quality(annotated)
        rejected_penalty = _score_rejected_keywords(annotated, rejected_keywords)
        profile_alignment = _score_keyword_alignment(annotated, profile_terms)
        taste_alignment = _score_keyword_alignment(annotated, taste_terms)

        total = (
            weights.get("topic_fit", 0.40) * topic_fit
            + weights.get("recency", 0.20) * recency
            + weights.get("novelty", 0.15) * novelty
            + weights.get("impact", 0.10) * impact
            + weights.get("venue_tier", 0.07) * venue_score
            + weights.get("author_preference", 0.05) * author_pref
            + weights.get("metadata_quality", 0.03) * metadata_quality
            + weights.get("profile_alignment", 0.05) * profile_alignment
            + weights.get("taste_alignment", 0.03) * taste_alignment
            + rejected_penalty
        )

        scored_paper = dict(annotated)
        scored_paper["best_topic"] = best_topic
        scored_paper["_score"] = round(total, 4)
        scored_paper["_score_breakdown"] = {
            "topic_fit": round(topic_fit, 4),
            "recency": round(recency, 4),
            "novelty": round(novelty, 4),
            "impact": round(impact, 4),
            "venue_tier": round(venue_score, 4),
            "author_preference": round(author_pref, 4),
            "metadata_quality": round(metadata_quality, 4),
            "profile_alignment": round(profile_alignment, 4),
            "taste_alignment": round(taste_alignment, 4),
            "rejected_penalty": round(rejected_penalty, 4),
        }
        scored.append(scored_paper)

    scored.sort(
        key=lambda item: (
            item["_score"],
            item["_score_breakdown"].get("topic_fit", 0),
            item["_score_breakdown"].get("venue_tier", 0),
            item.get("year") or 0,
        ),
        reverse=True,
    )
    return scored
