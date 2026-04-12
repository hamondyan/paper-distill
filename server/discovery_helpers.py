"""Discovery workflow helpers: query construction, diversity enforcement, drift detection.

Note: _enrich_inbox_candidate is intentionally kept in server_runtime.py because
it calls the resolve_metadata MCP tool function, which would create a circular import.
"""
from __future__ import annotations

import re
from pathlib import Path

from server.config import get_scoring_settings
from server.paper_scoring import _safe_parse_date, _tokenize
from server.paper_utils import first_author_surname


def _search_query_for_topic(topic_key: str, topic: dict) -> str:
    keywords = topic.get("keywords", [])
    aliases = topic.get("aliases", [])
    must_include = topic.get("must_include", [])
    must_exclude = topic.get("must_exclude", [])
    parts = [str(kw) for kw in keywords]
    parts.extend(str(a) for a in aliases)
    if must_include:
        parts.extend(f"+{term}" for term in must_include)
    if must_exclude:
        parts.extend(f"-{term}" for term in must_exclude)
    if parts:
        return " ".join(parts)
    return topic.get("label", topic_key)


def _limit_by_diversity(papers: list[dict], cap: int) -> list[dict]:
    """Enforce two diversity constraints: title-cluster cap AND author cap."""
    if cap <= 0:
        return papers
    author_cap = max(cap, 2)  # at least 2 per author
    clusters: dict[str, int] = {}
    author_counts: dict[str, int] = {}
    kept: list[dict] = []
    for paper in papers:
        # Title cluster diversity
        cluster_key = " ".join(sorted(_tokenize(paper.get("title", "")))) or str(paper.get("paper_id", ""))
        clusters.setdefault(cluster_key, 0)
        if clusters[cluster_key] >= cap:
            continue
        # Author diversity
        surname = first_author_surname(paper)
        if surname:
            author_counts.setdefault(surname, 0)
            if author_counts[surname] >= author_cap:
                continue
            author_counts[surname] += 1
        clusters[cluster_key] += 1
        kept.append(paper)
    return kept


def _extract_markdown_section(content: str, heading: str) -> str:
    pattern = re.compile(
        rf"^## {re.escape(heading)}\n+(.*?)(?=^## |\Z)",
        re.MULTILINE | re.DOTALL,
    )
    match = pattern.search(content)
    if not match:
        return ""
    return match.group(1).strip()


def _load_candidate_sections(vault_path: str, note_rel_path: str) -> dict[str, str]:
    note_path = Path(vault_path) / note_rel_path
    if not note_path.exists():
        return {}

    content = note_path.read_text(encoding="utf-8")
    links = _extract_markdown_section(content, "Links")
    open_access_url = ""
    pdf_url = ""
    html_url = ""
    if links:
        pdf_match = re.search(r"- PDF:\s+(https?://\S+)", links)
        html_match = re.search(r"- HTML:\s+(https?://\S+)", links)
        open_access_match = re.search(r"- Open access:\s+(https?://\S+)", links)
        if pdf_match:
            pdf_url = pdf_match.group(1)
        if html_match:
            html_url = html_match.group(1)
        if open_access_match:
            open_access_url = open_access_match.group(1)

    return {
        "summary": _extract_markdown_section(content, "Summary"),
        "abstract": _extract_markdown_section(content, "Abstract"),
        "why_recommended": _extract_markdown_section(content, "Why Recommended"),
        "open_access_url": open_access_url or pdf_url,
        "canonical_pdf_url": pdf_url,
        "canonical_html_url": html_url,
    }


def _candidate_already_processed(candidate: dict, existing_raw_ids: set[str]) -> bool:
    pid = str(candidate.get("paper_id", "")).lower()
    return (
        not pid
        or pid in existing_raw_ids
        or candidate.get("capture_status") == "succeeded"
        or candidate.get("wiki_paper_path")
    )


def _diagnose_discovery_drift(
    scored: list[dict],
    topic: dict,
    coverage_threshold: float = 0.30,
    off_topic_threshold: float = 0.60,
) -> dict:
    """Diagnose whether scored results have drifted from the target topic.

    Returns dict with 'drifted' bool and optional 'exclude_terms' for refinement.
    """
    keyword_tokens: set[str] = set()
    for kw in topic.get("keywords", []):
        keyword_tokens.update(_tokenize(kw))
    for alias in topic.get("aliases", []):
        keyword_tokens.update(_tokenize(alias))

    if not keyword_tokens or not scored:
        return {"drifted": False}

    # Check keyword coverage: how many papers mention at least one keyword
    covered = 0
    for paper in scored:
        paper_tokens = _tokenize(
            f"{paper.get('title', '')} {paper.get('abstract', '')}"
        )
        if paper_tokens & keyword_tokens:
            covered += 1
    coverage = covered / len(scored)

    # Check venue drift: count papers from clearly off-topic venues
    scoring_settings = get_scoring_settings()
    known_venues: set[str] = set()
    for tier in scoring_settings.get("venue_tiers", {}).values():
        known_venues.update(v.lower() for v in tier)

    off_topic_count = 0
    off_topic_venues: dict[str, int] = {}
    for paper in scored:
        venue = (paper.get("venue_normalized") or paper.get("venue") or "").lower()
        if venue and venue not in known_venues and "arxiv" not in venue:
            off_topic_count += 1
            off_topic_venues[venue] = off_topic_venues.get(venue, 0) + 1
    off_topic_ratio = off_topic_count / len(scored)

    drifted = coverage < coverage_threshold or off_topic_ratio > off_topic_threshold
    exclude_terms = []
    if drifted:
        # Suggest excluding the most frequent off-topic venue keywords
        for venue, count in sorted(off_topic_venues.items(), key=lambda x: -x[1])[:3]:
            for token in _tokenize(venue):
                if token not in keyword_tokens and len(token) > 3:
                    exclude_terms.append(token)
                    break

    return {
        "drifted": drifted,
        "keyword_coverage": coverage,
        "off_topic_venue_ratio": off_topic_ratio,
        "exclude_terms": exclude_terms[:3],
    }
