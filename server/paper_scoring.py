"""Paper scoring engine and text utility helpers.

Pure-computation module: no I/O, no vault access, no MCP concerns.
All scoring functions, text normalisation utilities, and the topic
canonicalisation helper live here so they can be tested in isolation.
"""
from __future__ import annotations

import math
import re
from datetime import datetime, timezone
from typing import Any

from dateutil.parser import parse as dateparse

from server.paper_utils import (
    canonical_html_url,
    canonical_item_url,
    canonical_pdf_url,
    normalize_venue_tier,
    paper_arxiv_id,
    paper_id,
)

# ---------------------------------------------------------------------------
# Text utilities
# ---------------------------------------------------------------------------


def _safe_citations(paper: dict) -> int | None:
    """Return citation count when available, otherwise ``None``."""
    c = paper.get("citation_count")
    if c is None or c == "":
        return None
    try:
        return max(0, int(c))
    except (ValueError, TypeError):
        return None


def _safe_parse_date(paper: dict) -> datetime | None:
    """Robust multi-format date parsing."""
    for field in ("published", "date", "year"):
        raw = paper.get(field)
        if raw:
            try:
                return dateparse(str(raw), fuzzy=True)
            except (ValueError, TypeError, OverflowError):
                continue
    return None


def _tokenize(text: str) -> set[str]:
    """Lowercase token set, min 2 chars."""
    return {w for w in re.split(r"\W+", text.lower()) if len(w) >= 2}


def _collapse_text(text: str) -> str:
    return " ".join((text or "").split()).strip()


def _annotate_paper(
    paper: dict,
    venue_aliases: dict[str, str] | None = None,
    venue_tiers: dict[str, list[str]] | None = None,
) -> dict:
    annotated = dict(paper)
    annotated["arxiv_id"] = annotated.get("arxiv_id") or paper_arxiv_id(annotated)
    venue_raw = annotated.get("venue", "") or ""
    venue_normalized, venue_tier = normalize_venue_tier(
        venue_raw,
        venue_aliases=venue_aliases,
        venue_tiers=venue_tiers,
    )
    annotated["venue_raw"] = venue_raw
    annotated["venue_normalized"] = venue_normalized
    annotated["venue_tier"] = venue_tier
    annotated["paper_id"] = annotated.get("paper_id") or paper_id(annotated)
    annotated["canonical_pdf_url"] = canonical_pdf_url(annotated)
    annotated["canonical_html_url"] = canonical_html_url(annotated)
    annotated["canonical_item_url"] = canonical_item_url(annotated)
    return annotated


# ---------------------------------------------------------------------------
# Topic canonicalisation
# ---------------------------------------------------------------------------


def _canonical_topics(
    topics: dict | None = None,
    topic_keywords: list[str] | None = None,
) -> dict[str, dict]:
    if topics:
        canonical = {}
        for key, value in topics.items():
            if isinstance(value, dict):
                canonical[key] = {
                    "label": value.get("label", key),
                    "keywords": value.get("keywords", []),
                    "aliases": value.get("aliases", []),
                    "must_include": value.get("must_include", []),
                    "must_exclude": value.get("must_exclude", []),
                }
        if canonical:
            return canonical

    if topic_keywords:
        return {
            "ad-hoc": {
                "label": "Ad Hoc Topic",
                "keywords": topic_keywords,
                "aliases": [],
                "must_include": [],
                "must_exclude": [],
            }
        }

    return {}


# ---------------------------------------------------------------------------
# Scoring constants
# ---------------------------------------------------------------------------

_ACRONYM_MAP: dict[str, str] = {
    "llm": "large language model",
    "llms": "large language models",
    "vlm": "vision language model",
    "vla": "vision language action",
    "rl": "reinforcement learning",
    "il": "imitation learning",
    "bc": "behavioral cloning",
    "vit": "vision transformer",
    "cnn": "convolutional neural network",
    "gan": "generative adversarial network",
    "diffusion": "denoising diffusion",
    "nerf": "neural radiance field",
    "slam": "simultaneous localization and mapping",
    "mpc": "model predictive control",
}


# ---------------------------------------------------------------------------
# Scoring functions
# ---------------------------------------------------------------------------


def _score_topic_fit(paper: dict, topic_keywords: list[str], topic_aliases: list[str] | None = None) -> float:
    title = paper.get("title", "")
    abstract = paper.get("abstract", "")
    venue = paper.get("venue_normalized", paper.get("venue", ""))
    paper_tokens = _tokenize(f"{title} {abstract} {venue}")
    keyword_tokens: set[str] = set()
    for kw in topic_keywords:
        keyword_tokens.update(_tokenize(kw))
    # Expand with aliases
    for alias in (topic_aliases or []):
        keyword_tokens.update(_tokenize(alias))
    # Expand with built-in acronym map
    expanded: set[str] = set()
    for token in keyword_tokens:
        if token in _ACRONYM_MAP:
            expanded.update(_tokenize(_ACRONYM_MAP[token]))
    keyword_tokens.update(expanded)
    if not keyword_tokens:
        return 0.0
    overlap = len(paper_tokens & keyword_tokens)
    return min(overlap / len(keyword_tokens), 1.0)


def _best_topic_fit(paper: dict, topics: dict[str, dict]) -> tuple[str, float]:
    best_topic = ""
    best_score = 0.0
    for topic_key, topic in topics.items():
        topic_keywords = topic.get("keywords", [])
        topic_aliases = topic.get("aliases", [])
        score = _score_topic_fit(paper, topic_keywords, topic_aliases)
        if score > best_score:
            best_topic = topic_key
            best_score = score
    return best_topic, best_score


def _score_recency_v2(paper: dict) -> float:
    now = datetime.now(timezone.utc)
    dt = _safe_parse_date(paper)

    if dt is not None and (
        paper.get("published") or paper.get("date")
    ):
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        days = max((now - dt).days, 0)
        if days <= 365:
            return 1.0
        if days <= 730:
            return 0.85
        if days <= 1460:
            return 0.60
        return 0.35

    year = paper.get("year")
    try:
        year_val = int(year)
    except (TypeError, ValueError):
        return 0.50

    age = max(now.year - year_val, 0)
    if age == 0:
        return 0.90
    if age == 1:
        return 0.80
    if age == 2:
        return 0.70
    if age <= 4:
        return 0.55
    return 0.40


def _score_impact_v2(paper: dict) -> float:
    citations = _safe_citations(paper)
    if citations is None:
        return 0.50
    cap = 200
    base = min(math.log(citations + 1) / math.log(cap + 1), 1.0)
    # Velocity bonus for papers older than 3 months
    dt = _safe_parse_date(paper)
    if dt is not None and citations > 0:
        now = datetime.now(timezone.utc)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        months = max((now - dt).days / 30.0, 1.0)
        if months >= 3:
            velocity = min(citations / months / 10.0, 0.3)
            return min(base + velocity, 1.0)
    return base


def _score_novelty_v2(paper: dict, known_ids: set[str]) -> float:
    pid = paper_id(paper)
    return 0.0 if pid in known_ids else 1.0


def _score_venue_tier_v2(paper: dict) -> float:
    tier = paper.get("venue_tier", "unknown")
    if tier == "tier_s":
        return 1.0
    if tier == "tier_a":
        return 0.80
    if tier == "workshop_or_unclear":
        return 0.30
    return 0.50


def _score_author_preference_v2(
    paper: dict,
    whitelist_authors: list[str] | None,
    preferred_venues: list[str] | None,
) -> float:
    authors = {str(author).strip().lower() for author in paper.get("authors", [])}
    whitelist = {author.strip().lower() for author in (whitelist_authors or [])}
    if authors & whitelist:
        return 1.0

    venue = str(paper.get("venue_normalized", "")).strip().lower()
    preferred = {venue_name.strip().lower() for venue_name in (preferred_venues or [])}
    if venue and venue in preferred:
        return 0.70
    return 0.0


def _score_metadata_quality_v2(paper: dict) -> float:
    checks = [
        bool(paper.get("abstract")),
        bool(paper.get("authors")),
        bool(paper.get("venue") or paper.get("venue_normalized")),
        bool(paper.get("open_access_url") or paper.get("doi")),
    ]
    return sum(1 for passed in checks if passed) / len(checks)


def _score_keyword_alignment(
    paper: dict,
    keywords: list[str] | None,
) -> float:
    """Return a bounded relevance boost from user/profile keywords."""
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
    paper: dict,
    rejected_keywords: list[str] | None,
) -> float:
    """Return a negative penalty if rejected keywords are found.

    Tiered penalties:
      - title match:    -0.80 (strongest signal — paper is *about* the rejected topic)
      - abstract match: -0.40 (moderate — could be related work mention)
      - venue match:    -0.15 (weak — venue covers broad area)

    Multiple matches within the same tier do NOT stack; the worst single tier
    penalty is returned.  This avoids over-punishing papers that mention a
    rejected term in *both* title and abstract.
    """
    if not rejected_keywords:
        return 0.0

    rejected_lower = [kw.strip().lower() for kw in rejected_keywords if kw.strip()]
    if not rejected_lower:
        return 0.0

    title = (paper.get("title") or "").lower()
    abstract = (paper.get("abstract") or "").lower()
    venue = (paper.get("venue_normalized") or paper.get("venue") or "").lower()

    worst = 0.0
    for kw in rejected_lower:
        if kw in title:
            worst = min(worst, -0.80)
        elif kw in abstract:
            worst = min(worst, -0.40)
        elif kw in venue:
            worst = min(worst, -0.15)
    return worst
