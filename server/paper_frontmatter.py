"""Frontmatter construction helpers for inbox, source-evidence, and wiki pages.

All functions build plain dicts; no file I/O happens here.
"""
from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any

from server.research_item import ResearchItem

# Fields that are updated when a higher-scoring discovery of the same paper
# arrives while a lower-scoring version already sits in the inbox.
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


def _canonical_url_updates(paper: dict) -> dict[str, str]:
    return {
        "canonical_html_url": paper.get("canonical_html_url", ""),
        "canonical_pdf_url": paper.get("canonical_pdf_url", ""),
    }


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
        "source_evidence_path": paper.get("source_evidence_path", ""),
        "wiki_paper_path": paper.get("wiki_paper_path", ""),
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
    prepared["source_evidence_path"] = ""
    prepared["wiki_paper_path"] = ""
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
    research_item: ResearchItem,
    appendix_policy: str,
    source_structured_rel_path: str = "",
    capture_method: str = "ar5iv_html_cleaned",
    capture_fidelity: str = "high",
    capture_source: str = "",
    figure_count: int = 0,
    table_count: int = 0,
    equation_count: int = 0,
) -> dict:
    return research_item.to_source_frontmatter(
        source_structured_path=source_structured_rel_path,
        appendix_policy=appendix_policy,
        capture_method=capture_method,
        capture_fidelity=capture_fidelity,
        capture_source=capture_source,
        figure_count=figure_count,
        table_count=table_count,
        equation_count=equation_count,
    )


def _wiki_frontmatter(
    research_item: ResearchItem,
    source_rel_path: str,
    source_structured_rel_path: str,
    zotero_mode: str,
    zotero_status: str,
    zotero_import_path: str,
    zotero_key: str,
    zotero_uri: str,
    confidence: float,
    capture_fidelity: str,
) -> dict:
    return research_item.to_wiki_frontmatter(
        source_evidence_path=source_rel_path,
        source_assets_path=source_structured_rel_path,
        zotero_mode=zotero_mode,
        zotero_status=zotero_status,
        zotero_import_path=zotero_import_path,
        zotero_uri=zotero_uri,
        zotero_key=zotero_key,
        confidence=0.0,
        capture_fidelity=capture_fidelity,
        page_state="pending-llm",
    )


def _successful_capture_updates(
    wiki_rel_path: str,
    source_rel_path: str,
    source_structured_rel_path: str,
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
        "source_evidence_path": source_rel_path,
        "wiki_paper_path": wiki_rel_path,
        "source_structured_path": source_structured_rel_path,
        **_canonical_url_updates(paper),
        "zotero_mode": zotero_mode,
        "zotero_status": zotero_status,
        "zotero_import_path": zotero_import_path,
        "zotero_key": zotero_key,
        "zotero_uri": zotero_uri,
        "page_state": "auto",
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
    wiki_path: Path,
) -> dict[str, str]:
    return {
        "paper_id": candidate.get("paper_id", ""),
        "zotero_mode": zotero_mode,
        "zotero_status": zotero_status,
        "zotero_import_path": zotero_import_path,
        "zotero_key": zotero_key,
        "zotero_uri": zotero_uri,
        "source_evidence_abs_path": str(source_path),
        "wiki_paper_abs_path": str(wiki_path),
        "page_state": "auto",
    }
