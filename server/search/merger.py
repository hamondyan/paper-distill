"""Deduplication and merge logic for multi-source paper results.

Primary dedup key: DOI (exact match).
Secondary: arXiv ID.
Then fuzzy title match (normalised, Jaccard similarity).
Merges metadata from duplicates: keeps the richer record.
"""
from __future__ import annotations

import logging
from typing import Any

from server.paper_utils import normalise_title, paper_arxiv_id, title_tokens, first_author_surname

LOG = logging.getLogger(__name__)

# Minimum Jaccard similarity for fuzzy title matching
_TITLE_SIM_THRESHOLD = 0.85

_SOURCE_PRIORITY = {
    "dblp": 400,
    "crossref": 300,
    "openalex": 250,
    "s2": 200,
    "pwc": 100,
    "arxiv": 0,
}


def _jaccard(a: set[str], b: set[str]) -> float:
    if not a or not b:
        return 0.0
    return len(a & b) / len(a | b)


def _year_value(paper: dict[str, Any]) -> str:
    """Extract year as a string for comparison."""
    y = paper.get("year") or paper.get("date", "")
    return str(y)[:4]


def _authors_year_match(a: dict[str, Any], b: dict[str, Any]) -> bool:
    """Check if two papers share first-author surname OR matching year.

    Used as secondary validation after fuzzy title match to prevent
    false-positive merges of papers with similar short titles.
    """
    surname_a = first_author_surname(a)
    surname_b = first_author_surname(b)
    if surname_a and surname_b and surname_a == surname_b:
        return True

    year_a = _year_value(a)
    year_b = _year_value(b)
    if year_a and year_b and len(year_a) == 4 and year_a == year_b:
        return True

    return False


def _source_priority_map(authority_order: list[str] | None = None) -> dict[str, int]:
    if not authority_order:
        return dict(_SOURCE_PRIORITY)
    count = len(authority_order)
    priority = {}
    for idx, source in enumerate(authority_order):
        priority[source] = (count - idx) * 100
    for source, score in _SOURCE_PRIORITY.items():
        priority.setdefault(source, score)
    return priority


def _source_rank(source_value: str, source_priority: dict[str, int] | None = None) -> int:
    priority = source_priority or _SOURCE_PRIORITY
    sources = [part.strip().lower() for part in str(source_value or "").split(",") if part.strip()]
    if not sources:
        return -1
    return max(priority.get(source, 0) for source in sources)


def _merge_into(
    existing: dict[str, Any],
    incoming: dict[str, Any],
    source_priority: dict[str, int] | None = None,
) -> None:
    """Merge *incoming* paper data into *existing*, mutating existing in place."""
    # Combine source tags
    sources = set(existing.get("source", "").split(","))
    sources.add(incoming.get("source", ""))
    existing["source"] = ",".join(sorted(s for s in sources if s))

    # Keep higher citation count
    existing_citations = existing.get("citation_count")
    incoming_citations = incoming.get("citation_count")
    if isinstance(incoming_citations, int) and (
        not isinstance(existing_citations, int) or incoming_citations > existing_citations
    ):
        existing["citation_count"] = incoming["citation_count"]

    existing_venue_source = existing.get("_venue_source", existing.get("source", ""))
    incoming_source = incoming.get("source", "")

    # Fill blank fields from incoming
    for field in (
        "doi", "arxiv_id", "abstract", "tldr", "open_access_url", "html_url", "code_url",
        "year", "published",
    ):
        if not existing.get(field) and incoming.get(field):
            existing[field] = incoming[field]

    incoming_venue = incoming.get("venue")
    if incoming_venue:
        if not existing.get("venue") or _source_rank(incoming_source, source_priority) > _source_rank(existing_venue_source, source_priority):
            existing["venue"] = incoming_venue
            existing["_venue_source"] = incoming_source

    # Merge authors if existing is empty
    if not existing.get("authors") and incoming.get("authors"):
        existing["authors"] = incoming["authors"]


def dedup_merge(
    papers: list[dict[str, Any]],
    authority_order: list[str] | None = None,
) -> list[dict[str, Any]]:
    """Deduplicate and merge a flat list of papers from multiple sources.

    Returns a new list with duplicates merged. Order is preserved (first seen wins
    position, later duplicates merge into the first).
    """
    merged: list[dict[str, Any]] = []
    source_priority = _source_priority_map(authority_order)
    doi_idx: dict[str, int] = {}          # doi -> index in merged
    arxiv_idx: dict[str, int] = {}        # arxiv id -> index in merged
    title_idx: dict[str, int] = {}        # normalised title -> index in merged
    title_tokens_cache: dict[int, set[str]] = {}  # merged index -> token set

    for p in papers:
        doi = (p.get("doi") or "").strip()
        arxiv_id = paper_arxiv_id(p)
        if arxiv_id:
            p["arxiv_id"] = arxiv_id
        norm_title = normalise_title(p.get("title", ""))

        match_idx: int | None = None

        # 1. Exact DOI match
        if doi and doi in doi_idx:
            match_idx = doi_idx[doi]

        # 2. Exact arXiv ID match
        if match_idx is None and arxiv_id and arxiv_id in arxiv_idx:
            match_idx = arxiv_idx[arxiv_id]

        # 3. Exact normalised title match
        if match_idx is None and norm_title and norm_title in title_idx:
            match_idx = title_idx[norm_title]

        # 4. Fuzzy title match (Jaccard on tokens) + author/year cross-validation
        if match_idx is None and norm_title:
            incoming_tokens = title_tokens(p.get("title", ""))
            if len(incoming_tokens) >= 3:  # skip very short titles
                for idx, cached_tokens in title_tokens_cache.items():
                    if _jaccard(incoming_tokens, cached_tokens) >= _TITLE_SIM_THRESHOLD:
                        # Cross-validate: author surname or year must also match
                        # to prevent false-positive merges of short-titled papers
                        if _authors_year_match(p, merged[idx]):
                            match_idx = idx
                            break

        if match_idx is not None:
            _merge_into(merged[match_idx], p, source_priority)
        else:
            idx = len(merged)
            item = dict(p)
            if item.get("venue"):
                item["_venue_source"] = item.get("source", "")
            merged.append(item)  # shallow copy
            if doi:
                doi_idx[doi] = idx
            if arxiv_id:
                arxiv_idx[arxiv_id] = idx
            if norm_title:
                title_idx[norm_title] = idx
                title_tokens_cache[idx] = title_tokens(p.get("title", ""))

    LOG.debug("dedup_merge: %d -> %d papers", len(papers), len(merged))
    return merged
