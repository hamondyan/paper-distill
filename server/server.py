"""Paper Distill MCP Server.

Search, scoring, vault querying, and lightweight deterministic workflow tools
for the Paper Distill knowledge system.
"""
from __future__ import annotations

import asyncio
import logging
import math
import re
from datetime import datetime, timezone
from pathlib import Path

from fastmcp import FastMCP

from server.arxiv_capture import (
    bind_paper_to_arxiv,
    build_crgp_dnl,
    capture_arxiv_source,
    clean_ar5iv_html,
)
from server.config import (
    get_env,
    get_paper_distill_settings,
    get_scoring_settings,
    get_topics,
    get_vault_path,
    get_zotero_collection_name,
    get_zotero_local_export_dir,
    get_zotero_mode,
    get_zotero_settings,
)
from server.paper_utils import (
    canonical_html_url,
    canonical_item_url,
    canonical_pdf_url,
    normalize_venue_tier,
    paper_arxiv_id,
    paper_id,
)
from server.search import (
    search_arxiv,
    search_semantic_scholar,
    search_openalex,
    search_dblp,
    search_papers_with_code,
    lookup_unpaywall,
    resolve_crossref,
    dedup_merge,
)
from server.vault_query import query_vault_sync
from server.vault_lint import (
    analyze_knowledge_graph_sync,
    lint_vault_sync,
    vault_stats_sync,
)
from server.vault_ops import (
    build_inbox_body,
    build_raw_note_body,
    build_raw_source_body,
    citekey_for_paper,
    ensure_vault_structure,
    inbox_note_path,
    raw_source_path,
    raw_note_path,
    update_frontmatter,
    write_markdown,
)
from server.zotero import add_papers as _zotero_add, search_papers as _zotero_search

logging.basicConfig(
    format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
    level=logging.INFO,
)
LOG = logging.getLogger("paper-distill")

mcp = FastMCP("paper-distill")

# Source registry
_SEARCH_SOURCES = {
    "arxiv": search_arxiv,
    "s2": search_semantic_scholar,
    "openalex": search_openalex,
    "dblp": search_dblp,
    "pwc": search_papers_with_code,
}

# Per-source timeout for circuit breaking
_SOURCE_TIMEOUT = 15  # seconds
_DISCOVERY_UPDATE_FIELDS = (
    "best_topic",
    "_score",
    "_score_breakdown",
    "why_recommended",
    "tldr",
    "abstract",
    "open_access_url",
    "venue_raw",
    "venue_normalized",
    "venue_tier",
    "venue_source",
    "arxiv_id",
    "canonical_pdf_url",
    "canonical_html_url",
    "canonical_item_url",
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

async def _search_with_timeout(fn, query: str, max_results: int, name: str):
    """Wrap a search coroutine with per-source timeout."""
    try:
        return await asyncio.wait_for(
            fn(query, max_results=max_results), _SOURCE_TIMEOUT
        )
    except asyncio.TimeoutError:
        LOG.warning("Search %s timed out after %ds", name, _SOURCE_TIMEOUT)
        return []
    except Exception as e:
        LOG.warning("Search %s failed: %s", name, e)
        return []


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
    from dateutil.parser import parse as dateparse

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


def _canonical_url_updates(paper: dict) -> dict[str, str]:
    return {
        "canonical_html_url": paper.get("canonical_html_url", ""),
        "canonical_pdf_url": paper.get("canonical_pdf_url", ""),
    }


def _mark_capture_failure(path: Path, paper: dict | None, error: str) -> dict[str, str]:
    updates = {
        "capture_status": "failed",
        "capture_error": error,
        **_canonical_url_updates(paper or {}),
    }
    update_frontmatter(path, updates)
    return updates


def _discover_frontmatter(paper: dict) -> dict:
    return {
        "paper_id": paper["paper_id"],
        "status": paper["status"],
        "title": paper.get("title", ""),
        "authors": paper.get("authors", []),
        "year": paper.get("year"),
        "doi": paper.get("doi", ""),
        "arxiv_id": paper.get("arxiv_id", ""),
        "sources": [src for src in paper.get("source", "").split(",") if src],
        "venue_raw": paper.get("venue_raw", ""),
        "venue_normalized": paper.get("venue_normalized", ""),
        "venue_tier": paper.get("venue_tier", "unknown"),
        "venue_source": paper.get("venue_source", ""),
        "best_topic": paper.get("best_topic", ""),
        "matched_topics": paper.get("matched_topics", []),
        "score_total": paper.get("_score", 0.0),
        "score_breakdown": paper.get("_score_breakdown", {}),
        "arxiv_binding_status": paper.get("arxiv_binding_status", "matched"),
        "capture_status": paper.get("capture_status", "pending"),
        "capture_error": paper.get("capture_error", ""),
        "summary": paper.get("tldr", ""),
        "abstract": paper.get("abstract", ""),
        "why_recommended": paper.get("why_recommended", ""),
        "open_access_url": paper.get("open_access_url", ""),
        "canonical_pdf_url": paper.get("canonical_pdf_url", ""),
        "canonical_html_url": paper.get("canonical_html_url", ""),
        "canonical_item_url": paper.get("canonical_item_url", ""),
        "raw_source_path": paper.get("raw_source_path", ""),
        "raw_note_path": paper.get("raw_note_path", ""),
        "zotero_mode": paper.get("zotero_mode", ""),
        "zotero_status": paper.get("zotero_status", ""),
        "zotero_import_path": paper.get("zotero_import_path", ""),
        "retrieved_at": paper["retrieved_at"],
        "decision_note": "",
    }


def _merge_discovered_paper(existing: dict, incoming: dict, topic_key: str) -> None:
    matched_topics = set(existing.get("matched_topics", []))
    matched_topics.add(topic_key)
    existing["matched_topics"] = sorted(matched_topics)
    if incoming.get("_score", 0.0) <= existing.get("_score", 0.0):
        return
    for field in _DISCOVERY_UPDATE_FIELDS:
        if incoming.get(field):
            existing[field] = incoming.get(field)


def _prepare_discovered_paper(paper: dict, topic_key: str, topic: dict) -> dict:
    prepared = dict(paper)
    prepared["matched_topics"] = [topic_key]
    prepared["status"] = "proposed"
    prepared["retrieved_at"] = datetime.now().date().isoformat()
    prepared["decision_note"] = ""
    prepared["arxiv_binding_status"] = prepared.get("arxiv_binding_status", "matched")
    prepared["capture_status"] = "pending"
    prepared["capture_error"] = ""
    prepared["raw_source_path"] = ""
    prepared["raw_note_path"] = ""
    prepared["venue_source"] = (
        prepared.get("venue_source")
        or prepared.get("_venue_source")
        or prepared.get("source", "")
    )
    prepared["why_recommended"] = (
        prepared.get("tldr")
        or f"High match for {topic.get('label', topic_key)} with score {paper.get('_score', 0):.2f}."
    )
    return prepared


def _source_frontmatter(
    paper: dict,
    candidate: dict,
    citekey: str,
    appendix_policy: str,
) -> dict:
    return {
        "paper_id": paper.get("paper_id", candidate.get("paper_id", "")),
        "citekey": citekey,
        "title": paper.get("title", ""),
        "authors": paper.get("authors", []),
        "year": paper.get("year"),
        "doi": paper.get("doi", ""),
        "arxiv_id": paper.get("arxiv_id", ""),
        "venue": paper.get("venue_raw") or paper.get("venue", ""),
        "venue_normalized": paper.get("venue_normalized", ""),
        "venue_tier": paper.get("venue_tier", "unknown"),
        "venue_source": paper.get("venue_source", ""),
        "topics": candidate.get("matched_topics", []),
        "canonical_html_url": paper.get("canonical_html_url", ""),
        "canonical_pdf_url": paper.get("canonical_pdf_url") or paper.get("open_access_url", ""),
        "capture_method": "ar5iv_html_cleaned",
        "appendix_policy": appendix_policy,
        "captured_at": datetime.now().isoformat(timespec="seconds"),
        "compiled": False,
    }


def _note_frontmatter(
    paper: dict,
    candidate: dict,
    citekey: str,
    source_rel_path: str,
    zotero_mode: str,
    zotero_status: str,
    zotero_import_path: str,
    zotero_key: str,
    zotero_uri: str,
    confidence: float,
) -> dict:
    return {
        "paper_id": paper.get("paper_id", candidate.get("paper_id", "")),
        "citekey": citekey,
        "title": paper.get("title", ""),
        "authors": paper.get("authors", []),
        "year": paper.get("year"),
        "doi": paper.get("doi", ""),
        "arxiv_id": paper.get("arxiv_id", ""),
        "venue": paper.get("venue_raw") or paper.get("venue", ""),
        "topics": candidate.get("matched_topics", []),
        "source_raw_path": source_rel_path,
        "zotero_mode": zotero_mode,
        "zotero_status": zotero_status,
        "zotero_import_path": zotero_import_path,
        "zotero_uri": zotero_uri,
        "zotero_key": zotero_key,
        "note_framework": "CRGP-DNL",
        "confidence": confidence,
        "compiled": False,
        "updated_at": datetime.now().isoformat(timespec="seconds"),
    }


def _successful_capture_updates(
    note_rel_path: str,
    source_rel_path: str,
    paper: dict,
    zotero_mode: str,
    zotero_status: str,
    zotero_import_path: str,
    zotero_key: str,
    zotero_uri: str,
) -> dict[str, str]:
    return {
        "processed_at": datetime.now().date().isoformat(),
        "capture_status": "succeeded",
        "capture_error": "",
        "raw_path": note_rel_path,
        "raw_source_path": source_rel_path,
        "raw_note_path": note_rel_path,
        **_canonical_url_updates(paper),
        "zotero_mode": zotero_mode,
        "zotero_status": zotero_status,
        "zotero_import_path": zotero_import_path,
        "zotero_key": zotero_key,
        "zotero_uri": zotero_uri,
    }


def _processed_error(candidate: dict, error: str) -> dict[str, str]:
    return {
        "paper_id": candidate.get("paper_id", ""),
        "error": error,
    }


def _processed_success(
    candidate: dict,
    zotero_mode: str,
    zotero_status: str,
    zotero_import_path: str,
    zotero_key: str,
    zotero_uri: str,
    source_path: Path,
    note_path: Path,
) -> dict[str, str]:
    return {
        "paper_id": candidate.get("paper_id", ""),
        "zotero_mode": zotero_mode,
        "zotero_status": zotero_status,
        "zotero_import_path": zotero_import_path,
        "zotero_key": zotero_key,
        "zotero_uri": zotero_uri,
        "raw_source_path": str(source_path),
        "raw_note_path": str(note_path),
    }


def _selected_topics(query: str | None, topic_keys: list[str] | None) -> dict[str, dict]:
    topics = get_topics()
    if query:
        return {
            "ad-hoc": {
                "label": query,
                "keywords": [query],
            }
        }
    return {
        key: value for key, value in topics.items()
        if not topic_keys or key in topic_keys
    }


def _capture_settings() -> tuple[str, int]:
    capture_settings = get_paper_distill_settings().get("capture", {})
    appendix_policy = str(capture_settings.get("appendix_policy", "summary_only"))
    min_body_chars = int(capture_settings.get("min_body_chars", 1500))
    return appendix_policy, min_body_chars


def _relative_to_vault_if_possible(vault_path: str, maybe_path: str) -> str:
    if not maybe_path:
        return ""
    target = Path(maybe_path).expanduser()
    try:
        return str(target.relative_to(Path(vault_path).expanduser()))
    except ValueError:
        return str(target)


def _zotero_runtime(vault_path: str) -> dict[str, str]:
    zotero_settings = get_zotero_settings()
    mode = get_zotero_mode()
    enabled = bool(zotero_settings.get("enabled", True))
    if not enabled:
        mode = "disabled"

    return {
        "mode": mode,
        "collection_name": get_zotero_collection_name(),
        "library_id": get_env("ZOTERO_LIBRARY_ID"),
        "api_key": get_env("ZOTERO_API_KEY"),
        "local_export_dir": get_zotero_local_export_dir(vault_path),
    }


async def _prepare_ingestion_candidate(
    candidate: dict,
    vault_path: str,
    collection_name: str,
    appendix_policy: str,
    min_body_chars: int,
) -> tuple[dict | None, Any | None, str]:
    paper = await _enrich_inbox_candidate(candidate, vault_path=vault_path)
    paper = await bind_paper_to_arxiv(paper) or {}
    if not paper:
        return None, None, "arXiv binding failed during ingestion"

    try:
        source_doc = await capture_arxiv_source(
            paper,
            appendix_policy=appendix_policy,
            min_body_chars=min_body_chars,
        )
    except Exception as exc:
        return None, None, str(exc)

    paper["title"] = source_doc.title or paper.get("title", "")
    paper["topic_tags"] = candidate.get("matched_topics", [])
    paper["collection_name"] = collection_name
    paper["venue_source"] = (
        paper.get("venue_source")
        or paper.get("_venue_source")
        or paper.get("source", "")
    )
    return paper, source_doc, ""


def _ingestion_paths(vault_path: str, paper: dict) -> tuple[str, Path, Path, str, str]:
    citekey = citekey_for_paper(paper)
    source_path = raw_source_path(vault_path, citekey)
    note_path = raw_note_path(vault_path, citekey)
    source_rel_path = str(source_path.relative_to(Path(vault_path)))
    note_rel_path = str(note_path.relative_to(Path(vault_path)))
    return citekey, source_path, note_path, source_rel_path, note_rel_path


def _note_body_payload(
    paper: dict,
    source_rel_path: str,
    zotero_mode: str,
    zotero_status: str,
    zotero_import_path: str,
    zotero_key: str,
    zotero_uri: str,
    dnl_note: dict,
) -> dict:
    note_paper = dict(paper)
    note_paper["zotero_mode"] = zotero_mode
    note_paper["zotero_status"] = zotero_status
    note_paper["zotero_import_path"] = zotero_import_path
    note_paper["zotero_uri"] = zotero_uri
    note_paper["zotero_key"] = zotero_key
    note_paper["source_raw_path"] = source_rel_path
    return {
        "paper": note_paper,
        "sections": dnl_note.get("sections", {}),
        "evidence": dnl_note.get("evidence", {}),
    }


async def _write_ingestion_outputs(
    vault_path: str,
    candidate: dict,
    paper: dict,
    source_doc: Any,
    appendix_policy: str,
    zotero_mode: str,
    zotero_status: str,
    zotero_import_path: str,
    zotero_key: str,
    zotero_uri: str,
    dnl_note: dict,
) -> tuple[Path, Path, str, str]:
    citekey, source_path, note_path, source_rel_path, note_rel_path = _ingestion_paths(vault_path, paper)
    await asyncio.to_thread(
        write_markdown,
        source_path,
        _source_frontmatter(paper, candidate, citekey, appendix_policy),
        build_raw_source_body(source_doc),
    )
    await asyncio.to_thread(
        write_markdown,
        note_path,
        _note_frontmatter(
            paper,
            candidate,
            citekey,
            source_rel_path,
            zotero_mode,
            zotero_status,
            zotero_import_path,
            zotero_key,
            zotero_uri,
            dnl_note.get("confidence", 0.5),
        ),
        build_raw_note_body(
            _note_body_payload(
                paper,
                source_rel_path,
                zotero_mode,
                zotero_status,
                zotero_import_path,
                zotero_key,
                zotero_uri,
                dnl_note,
            )
        ),
    )
    return source_path, note_path, source_rel_path, note_rel_path


def _existing_paper_ids(vault_path: str, sections: tuple[str, ...] = ("inbox", "raw", "papers")) -> set[str]:
    known: set[str] = set()
    for section in sections:
        data = query_vault_sync(vault_path, section=section)
        for item in data.get("sections", {}).get(section, []):
            pid = str(item.get("paper_id", "")).strip()
            if pid:
                known.add(pid)
            doi = str(item.get("doi", "")).strip().lower()
            if doi:
                known.add(f"doi:{doi}")
            arxiv_id = str(item.get("arxiv_id", "")).strip().lower()
            if arxiv_id:
                known.add(f"arxiv:{arxiv_id}")
    return known


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
                }
        if canonical:
            return canonical

    if topic_keywords:
        return {
            "ad-hoc": {
                "label": "Ad Hoc Topic",
                "keywords": topic_keywords,
            }
        }

    return {}


def _score_topic_fit(paper: dict, topic_keywords: list[str]) -> float:
    title = paper.get("title", "")
    abstract = paper.get("abstract", "")
    venue = paper.get("venue_normalized", paper.get("venue", ""))
    paper_tokens = _tokenize(f"{title} {abstract} {venue}")
    keyword_tokens = set()
    for kw in topic_keywords:
        keyword_tokens.update(_tokenize(kw))
    if not keyword_tokens:
        return 0.0
    overlap = len(paper_tokens & keyword_tokens)
    return min(overlap / len(keyword_tokens), 1.0)


def _best_topic_fit(paper: dict, topics: dict[str, dict]) -> tuple[str, float]:
    best_topic = ""
    best_score = 0.0
    for topic_key, topic in topics.items():
        topic_keywords = topic.get("keywords", [])
        score = _score_topic_fit(paper, topic_keywords)
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
    return min(math.log(citations + 1) / math.log(cap + 1), 1.0)


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


# ---------------------------------------------------------------------------
# Tool 1: search_papers
# ---------------------------------------------------------------------------

@mcp.tool()
async def search_papers(
    query: str,
    sources: list[str] | None = None,
    max_results: int = 20,
) -> list[dict]:
    """Search academic papers across CS/AI sources.

    Returns deduplicated, merged results enriched with stable paper IDs and
    normalized venue metadata.
    No ranking or filtering applied — the calling AI handles curation.

    Available sources: arxiv, s2 (Semantic Scholar), openalex, dblp, pwc (Papers with Code).

    Args:
        query: Search query string (e.g. "vision language action model")
        sources: List of source keys to search. Defaults to all 5.
        max_results: Maximum results per source (default 20)
    """
    if sources is None:
        sources = list(_SEARCH_SOURCES.keys())

    tasks = []
    source_names = []
    for src in sources:
        fn = _SEARCH_SOURCES.get(src)
        if fn:
            tasks.append(_search_with_timeout(fn, query, max_results, src))
            source_names.append(src)

    if not tasks:
        return []

    results = await asyncio.gather(*tasks)

    all_papers = []
    for name, res in zip(source_names, results):
        if res:
            LOG.info("Search %s: %d results", name, len(res))
            all_papers.extend(res)
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
    LOG.info("Total: %d papers after dedup (from %d raw)", len(merged), len(all_papers))
    return merged


# ---------------------------------------------------------------------------
# Tool 2: resolve_metadata
# ---------------------------------------------------------------------------

@mcp.tool()
async def resolve_metadata(doi: str) -> dict:
    """Resolve full metadata for a DOI via CrossRef + Unpaywall OA lookup.

    Returns combined metadata including title, authors, year, venue,
    abstract, open_access_url, and more. Useful for enriching papers
    that only have a DOI.

    Args:
        doi: The DOI to resolve (e.g. "10.48550/arxiv.2410.24164")
    """
    crossref_task = resolve_crossref(doi)
    unpaywall_task = lookup_unpaywall(doi)

    crossref_data, unpaywall_data = await asyncio.gather(
        crossref_task, unpaywall_task, return_exceptions=True
    )

    result = {}
    if isinstance(crossref_data, dict):
        result.update(crossref_data)
    elif isinstance(crossref_data, Exception):
        LOG.warning("CrossRef lookup failed for %s: %s", doi, crossref_data)

    if isinstance(unpaywall_data, dict):
        if unpaywall_data.get("best_oa_url"):
            result["open_access_url"] = unpaywall_data["best_oa_url"]
        result["is_oa"] = unpaywall_data.get("is_oa", False)
    elif isinstance(unpaywall_data, Exception):
        LOG.warning("Unpaywall lookup failed for %s: %s", doi, unpaywall_data)

    result["doi"] = doi
    return result


# ---------------------------------------------------------------------------
# Tool 3: zotero_add
# ---------------------------------------------------------------------------

@mcp.tool()
async def zotero_add(papers: list[dict]) -> list[dict]:
    """Add papers to Zotero library with auto-metadata enrichment.

    Dispatches through the configured Zotero mode:
    - ``local_first`` writes local CSL-JSON import packs
    - ``web_api`` creates journal-article items in the remote library
    - ``disabled`` records a skipped handoff

    Args:
        papers: List of paper dicts with at least 'doi' or 'title'.
                Each dict can have: title, authors, year, doi, abstract,
                venue, topic_tags, tldr, citekey.
    """
    zotero_runtime = _zotero_runtime(get_vault_path() or ".")
    mode = zotero_runtime["mode"]
    library_id = zotero_runtime["library_id"]
    api_key = zotero_runtime["api_key"]

    return await _zotero_add(
        papers,
        library_id,
        api_key,
        mode=mode,
        export_dir=zotero_runtime["local_export_dir"],
    )


# ---------------------------------------------------------------------------
# Tool 4: zotero_search
# ---------------------------------------------------------------------------

@mcp.tool()
async def zotero_search(query: str, limit: int = 20) -> list[dict]:
    """Search existing papers in Zotero library.

    Args:
        query: Search query string
        limit: Maximum results (default 20)
    """
    zotero_runtime = _zotero_runtime(get_vault_path() or ".")
    return await _zotero_search(
        query,
        zotero_runtime["library_id"],
        zotero_runtime["api_key"],
        limit=limit,
        mode=zotero_runtime["mode"],
    )


# ---------------------------------------------------------------------------
# Tool 5: fetch_pdf_text (async + ar5iv fallback + noise cleaning)
# ---------------------------------------------------------------------------

def _extract_pdf_sync(pdf_bytes: bytes, max_pages: int) -> str:
    """Synchronous PDF text extraction via PyMuPDF."""
    import fitz  # PyMuPDF

    doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    pages = min(len(doc), max_pages)
    text_parts = [doc[i].get_text() for i in range(pages)]
    doc.close()
    text = "\n\n".join(text_parts)

    # Strip reference section
    ref_pattern = re.compile(
        r"\n(?:References|Bibliography|REFERENCES)\s*\n.*", re.DOTALL
    )
    text = ref_pattern.sub("", text)

    # Strip page headers/footers (lines that are just numbers or very short)
    lines = [
        line
        for line in text.split("\n")
        if len(line.strip()) > 5 or not line.strip().isdigit()
    ]
    return "\n".join(lines)


def _clean_ar5iv_html(html: str) -> str:
    """Extract readable prose from ar5iv HTML using the v2.1 cleaner."""
    return clean_ar5iv_html(html).markdown


def _extract_arxiv_id(url: str) -> str | None:
    """Extract arXiv ID from URL or DOI."""
    # From URL: arxiv.org/abs/2410.24164 or arxiv.org/pdf/2410.24164
    m = re.search(r"arxiv\.org/(?:abs|pdf)/(\d{4}\.\d{4,5}(?:v\d+)?)", url)
    if m:
        return m.group(1)
    # From DOI: 10.48550/arxiv.2410.24164
    m = re.search(r"arxiv\.(\d{4}\.\d{4,5})", url, re.IGNORECASE)
    if m:
        return m.group(1)
    return None


@mcp.tool()
async def fetch_pdf_text(url: str, max_pages: int = 10) -> str:
    """Fetch and extract text from an open-access paper.

    For arXiv papers, tries ar5iv HTML first (faster, cleaner), then falls
    back to PDF. For other URLs, fetches PDF directly.

    Args:
        url: Direct URL to a PDF file, or an arXiv abs/pdf URL
        max_pages: Maximum pages to extract from PDF (default 10)
    """
    import httpx

    arxiv_id = _extract_arxiv_id(url)

    # Try ar5iv HTML first for arXiv papers
    if arxiv_id:
        ar5iv_url = f"https://ar5iv.labs.arxiv.org/html/{arxiv_id}"
        try:
            async with httpx.AsyncClient(timeout=30, follow_redirects=True) as client:
                resp = await client.get(ar5iv_url)
                if resp.status_code == 200:
                    text = await asyncio.to_thread(_clean_ar5iv_html, resp.text)
                    if len(text) > 500:  # sanity check: got meaningful content
                        LOG.info("ar5iv HTML extraction succeeded for %s", arxiv_id)
                        return text
                    LOG.info("ar5iv returned sparse content, falling back to PDF")
        except Exception as e:
            LOG.info("ar5iv failed for %s: %s, falling back to PDF", arxiv_id, e)

    # PDF fallback
    try:
        async with httpx.AsyncClient(timeout=60, follow_redirects=True) as client:
            resp = await client.get(url)
            resp.raise_for_status()
            pdf_bytes = resp.content
    except Exception as e:
        return f"Error fetching PDF: {e}"

    try:
        text = await asyncio.to_thread(_extract_pdf_sync, pdf_bytes, max_pages)
        return text
    except ImportError:
        return "Error: PyMuPDF (fitz) not installed. Add 'pymupdf' to dependencies."
    except Exception as e:
        return f"Error extracting PDF text: {e}"


# ---------------------------------------------------------------------------
# Tool 6: score_papers (v2 topic-aware deterministic formula)
# ---------------------------------------------------------------------------

@mcp.tool()
async def score_papers(
    papers: list[dict],
    topic_keywords: list[str] | None = None,
    known_dois: list[str] | None = None,
    topics: dict | None = None,
    known_ids: list[str] | None = None,
    whitelist_authors: list[str] | None = None,
    preferred_venues: list[str] | None = None,
    venue_aliases: dict | None = None,
    venue_tiers: dict | None = None,
) -> list[dict]:
    """Score papers using the v2 topic-aware deterministic formula."""
    settings = get_paper_distill_settings()
    scoring_settings = settings.get("scoring", {})
    weights = scoring_settings.get("weights", {})
    topics_map = _canonical_topics(topics=topics, topic_keywords=topic_keywords)

    if not topics_map:
        topics_map = _canonical_topics(topics=get_topics())

    aliases = venue_aliases or scoring_settings.get("venue_aliases", {})
    tiers = venue_tiers or scoring_settings.get("venue_tiers", {})
    preferred_venues = preferred_venues or settings.get("research_profile", {}).get(
        "learned_preferences", {}
    ).get("preferred_venues", [])
    whitelist_authors = whitelist_authors or settings.get("research_profile", {}).get(
        "whitelist_authors", []
    )

    known_id_set = {item.strip().lower() for item in (known_ids or []) if item}
    known_id_set.update(
        f"doi:{doi.strip().lower()}" for doi in (known_dois or []) if doi
    )
    scored = []

    for p in papers:
        annotated = _annotate_paper(p, venue_aliases=aliases, venue_tiers=tiers)
        best_topic, topic_fit = _best_topic_fit(annotated, topics_map)
        rec = _score_recency_v2(annotated)
        nov = _score_novelty_v2(annotated, known_id_set)
        imp = _score_impact_v2(annotated)
        venue_score = _score_venue_tier_v2(annotated)
        author_pref = _score_author_preference_v2(
            annotated,
            whitelist_authors=whitelist_authors,
            preferred_venues=preferred_venues,
        )
        metadata_quality = _score_metadata_quality_v2(annotated)

        total = (
            weights.get("topic_fit", 0.40) * topic_fit
            + weights.get("recency", 0.20) * rec
            + weights.get("novelty", 0.15) * nov
            + weights.get("impact", 0.10) * imp
            + weights.get("venue_tier", 0.07) * venue_score
            + weights.get("author_preference", 0.05) * author_pref
            + weights.get("metadata_quality", 0.03) * metadata_quality
        )

        scored_paper = dict(annotated)
        scored_paper["best_topic"] = best_topic
        scored_paper["_score"] = round(total, 4)
        scored_paper["_score_breakdown"] = {
            "topic_fit": round(topic_fit, 4),
            "recency": round(rec, 4),
            "novelty": round(nov, 4),
            "impact": round(imp, 4),
            "venue_tier": round(venue_score, 4),
            "author_preference": round(author_pref, 4),
            "metadata_quality": round(metadata_quality, 4),
        }
        scored.append(scored_paper)

    scored.sort(
        key=lambda x: (
            x["_score"],
            x["_score_breakdown"].get("topic_fit", 0),
            x["_score_breakdown"].get("venue_tier", 0),
            x.get("year") or 0,
        ),
        reverse=True,
    )
    return scored


# ---------------------------------------------------------------------------
# Tool 7: query_vault (AI's interface to vault state)
# ---------------------------------------------------------------------------

@mcp.tool()
async def query_vault(
    section: str = "all",
    topic: str | None = None,
    uncompiled_only: bool = False,
    status: str | None = None,
) -> dict:
    """Query the Paper Distill vault metadata by parsing YAML frontmatter.

    This is the AI's interface to vault state. Use this instead of reading
    _index.md files (which contain Dataview queries for Obsidian rendering,
    not actual data).

    Args:
        section: "inbox", "raw", "raw_source", "raw_notes", "papers", "concepts",
            "methods", "topics", or "all"
        topic: Filter by topic tag (optional)
        uncompiled_only: If True, only return raw papers not yet compiled
        status: Filter inbox notes by status (optional)

    Returns:
        Dict with "stats" (per-section counts) and "sections" (per-section
        item lists with frontmatter metadata).
    """
    vault_path = get_vault_path()
    if not vault_path:
        return {"error": "VAULT_PATH not configured. Set it in settings.json or env."}

    return await asyncio.to_thread(
        query_vault_sync, vault_path, section, topic, uncompiled_only, status
    )


# ---------------------------------------------------------------------------
# Tool 8: bootstrap_vault
# ---------------------------------------------------------------------------

@mcp.tool()
async def bootstrap_vault(vault_path: str | None = None) -> dict:
    """Initialize the Paper Distill directory structure inside an Obsidian vault."""
    target = vault_path or get_vault_path()
    if not target:
        return {"error": "VAULT_PATH not configured. Set it in settings.json or env."}

    root = await asyncio.to_thread(ensure_vault_structure, target)
    return {
        "vault_path": target,
        "paper_distill_root": str(root),
    }


def _search_query_for_topic(topic_key: str, topic: dict) -> str:
    keywords = topic.get("keywords", [])
    if keywords:
        return " ".join(str(keyword) for keyword in keywords)
    return topic.get("label", topic_key)


def _limit_by_diversity(papers: list[dict], cap: int) -> list[dict]:
    if cap <= 0:
        return papers
    clusters: dict[str, int] = {}
    kept: list[dict] = []
    for paper in papers:
        cluster_key = " ".join(sorted(_tokenize(paper.get("title", "")))) or str(paper.get("paper_id", ""))
        clusters.setdefault(cluster_key, 0)
        if clusters[cluster_key] >= cap:
            continue
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


async def _enrich_inbox_candidate(candidate: dict, vault_path: str | None = None) -> dict:
    enriched = dict(candidate)
    if not enriched.get("venue") and enriched.get("venue_raw"):
        enriched["venue"] = enriched.get("venue_raw")

    note_rel_path = str(enriched.get("_path", "")).strip()
    if vault_path and note_rel_path:
        note_sections = _load_candidate_sections(vault_path, note_rel_path)
        for field in (
            "summary",
            "abstract",
            "why_recommended",
            "open_access_url",
            "canonical_pdf_url",
            "canonical_html_url",
        ):
            if note_sections.get(field) and not enriched.get(field):
                enriched[field] = note_sections[field]

    doi = str(enriched.get("doi", "")).strip()
    needs_metadata = any(
        not enriched.get(field)
        for field in ("abstract", "open_access_url")
    )
    if doi and needs_metadata:
        resolved = await resolve_metadata(doi)
        if isinstance(resolved, dict):
            for field in (
                "title",
                "authors",
                "year",
                "venue",
                "abstract",
                "open_access_url",
            ):
                if resolved.get(field) and not enriched.get(field):
                    enriched[field] = resolved.get(field)

    scoring_settings = get_scoring_settings()
    return _annotate_paper(
        enriched,
        venue_aliases=scoring_settings.get("venue_aliases", {}),
        venue_tiers=scoring_settings.get("venue_tiers", {}),
    )


def _candidate_already_processed(candidate: dict, existing_raw_ids: set[str]) -> bool:
    pid = str(candidate.get("paper_id", "")).lower()
    return (
        not pid
        or pid in existing_raw_ids
        or candidate.get("capture_status") == "succeeded"
        or candidate.get("raw_note_path")
    )


# ---------------------------------------------------------------------------
# Tool 9: discover_papers
# ---------------------------------------------------------------------------

@mcp.tool()
async def discover_papers(
    query: str | None = None,
    topic_keys: list[str] | None = None,
    max_results_per_source: int | None = None,
    save_to_inbox: bool = True,
) -> dict:
    """Search, score, arXiv-bind, and optionally save candidate papers into inbox notes."""
    settings = get_paper_distill_settings()
    selected_topics = _selected_topics(query, topic_keys)

    if not selected_topics:
        return {"error": "No topics available for discovery."}

    vault_path = get_vault_path()
    if save_to_inbox and not vault_path:
        return {"error": "VAULT_PATH not configured. Set it in settings.json or env."}

    if save_to_inbox:
        await asyncio.to_thread(ensure_vault_structure, vault_path)

    search_sources = settings.get("search", {}).get("sources", list(_SEARCH_SOURCES.keys()))
    max_per_source = max_results_per_source or settings.get("search", {}).get("max_per_topic", 20)
    max_candidates = settings.get("workflow", {}).get("max_candidates_per_topic", 5)
    diversity_cap = settings.get("workflow", {}).get("diversity_cap_per_cluster", 2)
    require_arxiv_binding = settings.get("workflow", {}).get("require_arxiv_binding", True)
    known_ids = _existing_paper_ids(vault_path) if vault_path else set()
    existing_in_vault_ids = set(known_ids)

    discovered: list[dict] = []
    discovered_by_id: dict[str, dict] = {}
    written: list[str] = []

    for topic_key, topic in selected_topics.items():
        search_query = query or _search_query_for_topic(topic_key, topic)
        results = await search_papers(
            query=search_query,
            sources=search_sources,
            max_results=max_per_source,
        )
        scored = await score_papers(
            papers=results,
            topics={topic_key: topic},
            known_ids=sorted(known_ids),
        )
        capped = _limit_by_diversity(scored, diversity_cap)[:max_candidates]
        for paper in capped:
            bound = await bind_paper_to_arxiv(paper) if require_arxiv_binding else dict(paper)
            if require_arxiv_binding and not bound:
                continue
            if not bound:
                continue
            pid = str(bound.get("paper_id", "")).lower()
            if not pid:
                continue
            if pid in existing_in_vault_ids:
                continue

            if pid in discovered_by_id:
                _merge_discovered_paper(discovered_by_id[pid], bound, topic_key)
                continue

            prepared = _prepare_discovered_paper(bound, topic_key, topic)
            discovered.append(prepared)
            discovered_by_id[pid] = prepared

    for paper in discovered:
        pid = str(paper.get("paper_id", "")).lower()
        if not pid:
            continue
        known_ids.add(pid)
        if save_to_inbox:
            note_path = await asyncio.to_thread(inbox_note_path, vault_path, paper)
            await asyncio.to_thread(
                write_markdown,
                note_path,
                _discover_frontmatter(paper),
                build_inbox_body(paper),
            )
            written.append(str(note_path))

    return {
        "topics": list(selected_topics.keys()),
        "papers": discovered,
        "written": written,
    }


# ---------------------------------------------------------------------------
# Tool 10: process_inbox
# ---------------------------------------------------------------------------

@mcp.tool()
async def process_inbox(
    status: str = "approved",
    limit: int = 20,
    collection_name: str = "",
) -> dict:
    """Capture approved inbox notes into source/note layers, then hand off to Zotero."""
    vault_path = get_vault_path()
    if not vault_path:
        return {"error": "VAULT_PATH not configured. Set it in settings.json or env."}

    zotero_runtime = _zotero_runtime(vault_path)
    collection = collection_name or zotero_runtime["collection_name"]
    if zotero_runtime["mode"] == "web_api" and (
        not zotero_runtime["library_id"] or not zotero_runtime["api_key"]
    ):
        return {"error": "ZOTERO_LIBRARY_ID and ZOTERO_API_KEY required for web_api mode"}

    appendix_policy, min_body_chars = _capture_settings()

    ensure_vault_structure(vault_path)
    inbox = query_vault_sync(vault_path, section="inbox", status=status)
    candidates = inbox.get("sections", {}).get("inbox", [])[:limit]
    existing_raw_ids = _existing_paper_ids(vault_path, sections=("raw", "raw_notes", "papers"))
    processed: list[dict] = []

    for candidate in candidates:
        pid = str(candidate.get("paper_id", "")).lower()
        if _candidate_already_processed(candidate, existing_raw_ids):
            continue

        inbox_note_abs = Path(vault_path) / candidate["_path"]
        paper, source_doc, error = await _prepare_ingestion_candidate(
            candidate,
            vault_path,
            collection,
            appendix_policy,
            min_body_chars,
        )
        if error:
            await asyncio.to_thread(
                _mark_capture_failure,
                inbox_note_abs,
                paper,
                error,
            )
            processed.append(_processed_error(candidate, error))
            continue

        dnl_note = build_crgp_dnl(paper, source_doc)
        paper["citekey"] = citekey_for_paper(paper)
        zotero_items = await _zotero_add(
            [paper],
            zotero_runtime["library_id"],
            zotero_runtime["api_key"],
            mode=zotero_runtime["mode"],
            export_dir=zotero_runtime["local_export_dir"],
        )
        if not zotero_items or zotero_items[0].get("error"):
            error_text = zotero_items[0].get("error", "Zotero add failed") if zotero_items else "Zotero add failed"
            await asyncio.to_thread(
                _mark_capture_failure,
                inbox_note_abs,
                paper,
                error_text,
            )
            processed.append(_processed_error(candidate, error_text))
            continue

        zotero_item = zotero_items[0]
        zotero_key = zotero_item.get("key", "")
        zotero_uri = zotero_item.get("zotero_uri", "")
        zotero_mode = zotero_item.get("zotero_mode", zotero_runtime["mode"])
        zotero_status = zotero_item.get("zotero_status", "cloud_synced" if zotero_uri else "")
        zotero_import_path = _relative_to_vault_if_possible(
            vault_path,
            zotero_item.get("zotero_import_path", ""),
        )
        source_path, note_path, source_rel_path, note_rel_path = await _write_ingestion_outputs(
            vault_path,
            candidate,
            paper,
            source_doc,
            appendix_policy,
            zotero_mode,
            zotero_status,
            zotero_import_path,
            zotero_key,
            zotero_uri,
            dnl_note,
        )

        await asyncio.to_thread(
            update_frontmatter,
            inbox_note_abs,
            _successful_capture_updates(
                note_rel_path,
                source_rel_path,
                paper,
                zotero_mode,
                zotero_status,
                zotero_import_path,
                zotero_key,
                zotero_uri,
            ),
        )
        existing_raw_ids.add(pid)
        processed.append(
            _processed_success(
                candidate,
                zotero_mode,
                zotero_status,
                zotero_import_path,
                zotero_key,
                zotero_uri,
                source_path,
                note_path,
            )
        )

    return {"processed": processed}


# ---------------------------------------------------------------------------
# Tool 11: lint_vault
# ---------------------------------------------------------------------------

@mcp.tool()
async def lint_vault() -> dict:
    """Run deterministic structural health checks on the vault.

    Checks for: orphaned articles, broken backlinks, missing frontmatter,
    stale indexes, uncompiled papers, and missing concept stubs.
    Returns a structured JSON report with counts and file lists.
    """
    vault_path = get_vault_path()
    if not vault_path:
        return {"error": "VAULT_PATH not configured."}
    return await asyncio.to_thread(lint_vault_sync, vault_path)


# ---------------------------------------------------------------------------
# Tool 12: vault_stats
# ---------------------------------------------------------------------------

@mcp.tool()
async def vault_stats() -> dict:
    """Compute vault statistics: paper counts per stage, compilation rate,
    wiki article counts, per-topic breakdowns, and last activity timestamp.
    """
    vault_path = get_vault_path()
    if not vault_path:
        return {"error": "VAULT_PATH not configured."}
    return await asyncio.to_thread(vault_stats_sync, vault_path)


# ---------------------------------------------------------------------------
# Tool 13: analyze_knowledge_graph
# ---------------------------------------------------------------------------

@mcp.tool()
async def analyze_knowledge_graph(user_topics: list[str] | None = None) -> dict:
    """Analyze the vault's concept-paper graph to find structural research gaps.

    Returns condensed gap lists (methodology mismatches, combination
    opportunities, recurring problems, scaling questions) that can be
    turned into qualitative research ideas by the LLM.

    Args:
        user_topics: The user's research topics for mismatch analysis.
                     If omitted, reads from settings.json.
    """
    vault_path = get_vault_path()
    if not vault_path:
        return {"error": "VAULT_PATH not configured."}
    if user_topics is None:
        topics_config = get_topics()
        user_topics = [t.get("key", t.get("name", "")) for t in topics_config]
    return await asyncio.to_thread(analyze_knowledge_graph_sync, vault_path, user_topics)


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main():
    mcp.run()


if __name__ == "__main__":
    main()
