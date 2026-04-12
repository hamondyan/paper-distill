"""Paper identification, deduplication, and text-extraction helpers.

Handles:
- Extracting structured information from raw PDF text
- Building stable identifier sets for deduplication
- Locating existing papers in the vault by identifier matching
"""
from __future__ import annotations

import re
from pathlib import Path
from typing import Any
from urllib.parse import unquote

from server.arxiv_capture import CleanedArxivDocument
from server.capture_settings import _selected_topics
from server.paper_scoring import _collapse_text, _score_topic_fit
from server.vault_query import query_vault_sync

_DOI_PATTERN = re.compile(r"10\.\d{4,9}/[-._;()/:A-Za-z0-9]+", re.IGNORECASE)


# ---------------------------------------------------------------------------
# Vault identifier scanning
# ---------------------------------------------------------------------------


def _existing_paper_ids(
    vault_path: str,
    sections: tuple[str, ...] = ("inbox", "source_evidence", "papers"),
) -> set[str]:
    known: set[str] = set()
    for section in sections:
        data = query_vault_sync(vault_path, section=section, detail="full")
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


# ---------------------------------------------------------------------------
# DOI extraction
# ---------------------------------------------------------------------------


def _extract_doi(value: str) -> str:
    text = unquote((value or "").strip())
    if text.lower().startswith("doi:"):
        text = text[4:].strip()
    match = _DOI_PATTERN.search(text)
    if not match:
        return ""
    return match.group(0).rstrip(").,;")


# ---------------------------------------------------------------------------
# PDF text extraction helpers
# ---------------------------------------------------------------------------


def _extract_title_from_text(text: str) -> str:
    for line in text.splitlines():
        candidate = _collapse_text(line)
        lowered = candidate.lower()
        if len(candidate) < 15 or len(candidate) > 220:
            continue
        if lowered in {"abstract", "introduction", "references"}:
            continue
        if lowered.startswith(("http", "doi:", "arxiv:")):
            continue
        return candidate
    return ""


def _extract_abstract_from_text(text: str) -> str:
    match = re.search(
        r"(?:^|\n)\s*abstract\s*\n+(.*?)(?=\n\s*(?:1\.?\s+introduction|introduction|keywords|contents)\b|\n\s*\n|\Z)",
        text,
        re.IGNORECASE | re.DOTALL,
    )
    if match:
        abstract = _collapse_text(match.group(1))
        if len(abstract) >= 60:
            return abstract

    paragraphs = [
        _collapse_text(chunk)
        for chunk in re.split(r"\n\s*\n", text)
    ]
    for paragraph in paragraphs:
        lowered = paragraph.lower()
        if len(paragraph) >= 80 and not lowered.startswith(("abstract", "keywords", "references")):
            return paragraph
    return ""


def _extract_year_from_text(text: str) -> int | None:
    match = re.search(r"\b(19|20)\d{2}\b", text[:2000])
    if not match:
        return None
    try:
        return int(match.group(0))
    except ValueError:
        return None


def _source_doc_from_text(
    paper: dict,
    text: str,
    min_body_chars: int,
) -> CleanedArxivDocument:
    paragraphs = [
        _collapse_text(chunk)
        for chunk in re.split(r"\n\s*\n", text)
    ]
    paragraphs = [paragraph for paragraph in paragraphs if len(paragraph) >= 40]
    if not paragraphs:
        raise ValueError("PDF text extraction returned too little structured content")

    title = paper.get("title") or _extract_title_from_text(text) or "Untitled Paper"
    abstract = paper.get("abstract") or _extract_abstract_from_text(text)
    body_paragraphs = paragraphs[: min(len(paragraphs), 24)]
    body_text = "\n\n".join(body_paragraphs)
    if len(body_text) < min_body_chars:
        raise ValueError(f"recovered PDF text too short ({len(body_text)} chars)")

    markdown = "\n".join(
        [
            f"# {title}",
            "",
            "## Abstract",
            "",
            abstract or "Abstract unavailable.",
            "",
            "## Recovered Text",
            "",
            body_text,
        ]
    ).strip()
    return CleanedArxivDocument(
        title=title,
        abstract=abstract,
        markdown=markdown,
        sections=[
            {
                "heading": "Recovered Text",
                "level": 2,
                "paragraphs": body_paragraphs,
                "captions": [],
            }
        ],
        appendix_snapshot=[],
        quality={
            "body_chars": len(body_text),
            "has_abstract": bool(abstract),
            "section_count": 1,
            "appendix_chars": 0,
            "appendix_sections": 0,
            "bibliography_ratio": 0.0,
        },
        capture_fidelity="low",
        capture_source="pdf_text",
        capture_method="pdf_text_recovered",
    )


def _source_doc_sidecar_payload(source_doc: CleanedArxivDocument) -> dict:
    return {
        "title": source_doc.title,
        "abstract": source_doc.abstract,
        "capture_fidelity": getattr(source_doc, "capture_fidelity", "unknown"),
        "capture_source": getattr(source_doc, "capture_source", ""),
        "capture_method": getattr(source_doc, "capture_method", ""),
        "quality": getattr(source_doc, "quality", {}),
        "sections": getattr(source_doc, "sections", []),
        "appendix_snapshot": getattr(source_doc, "appendix_snapshot", []),
        "figures": getattr(source_doc, "figures", []),
        "tables": getattr(source_doc, "tables", []),
        "equations": getattr(source_doc, "equations", []),
    }


# ---------------------------------------------------------------------------
# Topic matching for explicit papers
# ---------------------------------------------------------------------------


def _explicit_candidate(paper: dict, matched_topics: list[str]) -> dict[str, Any]:
    best_topic = matched_topics[0] if matched_topics else ""
    return {
        "paper_id": paper.get("paper_id", ""),
        "matched_topics": matched_topics,
        "best_topic": best_topic,
    }


def _matched_topics_for_explicit_paper(
    paper: dict,
    topic_keys: list[str] | None = None,
) -> list[str]:
    selected = _selected_topics(None, topic_keys)
    if not selected:
        return []

    scored: list[tuple[float, str]] = []
    for topic_key, topic in selected.items():
        score = _score_topic_fit(paper, topic.get("keywords", []))
        if score > 0:
            scored.append((score, topic_key))

    scored.sort(key=lambda item: (-item[0], item[1]))
    if scored:
        return [topic_key for _, topic_key in scored]
    if topic_keys:
        return list(dict.fromkeys(topic_keys))
    return []


# ---------------------------------------------------------------------------
# Identifier-based deduplication
# ---------------------------------------------------------------------------


def _candidate_identifiers(paper: dict) -> set[str]:
    identifiers: set[str] = set()
    pid = str(paper.get("paper_id", "")).strip().lower()
    has_stable_metadata = bool(
        paper.get("doi")
        or paper.get("arxiv_id")
        or paper.get("title")
        or paper.get("authors")
        or paper.get("year")
    )
    if pid and (not pid.startswith("hash:") or has_stable_metadata):
        identifiers.add(pid)
    doi = str(paper.get("doi", "")).strip().lower()
    if doi:
        identifiers.add(f"doi:{doi}")
    arxiv_id = str(paper.get("arxiv_id", "")).strip().lower()
    if arxiv_id:
        identifiers.add(f"arxiv:{arxiv_id}")
    for url in (
        paper.get("canonical_item_url", ""),
        paper.get("canonical_pdf_url", ""),
        paper.get("open_access_url", ""),
        paper.get("url", ""),
    ):
        cleaned = str(url).strip().lower()
        if cleaned:
            identifiers.add(f"url:{cleaned}")
    return identifiers


def _matches_existing_item(item: dict, identifiers: set[str]) -> bool:
    item_ids = {
        str(item.get("paper_id", "")).strip().lower(),
        f"doi:{str(item.get('doi', '')).strip().lower()}",
        f"arxiv:{str(item.get('arxiv_id', '')).strip().lower()}",
        f"url:{str(item.get('canonical_item_url', '')).strip().lower()}",
        f"url:{str(item.get('canonical_pdf_url', '')).strip().lower()}",
        f"url:{str(item.get('open_access_url', '')).strip().lower()}",
    }
    item_ids.discard("")
    item_ids.discard("doi:")
    item_ids.discard("arxiv:")
    item_ids.discard("url:")
    return bool(item_ids & identifiers)


def _abs_vault_path(vault_path: str, rel_path: str) -> str:
    if not rel_path:
        return ""
    return str((Path(vault_path).expanduser() / rel_path).resolve())


def _find_existing_paper(vault_path: str, paper: dict) -> dict[str, Any] | None:
    identifiers = _candidate_identifiers(paper)
    if not identifiers:
        return None

    source_evidence = query_vault_sync(vault_path, section="source_evidence", detail="full").get("sections", {}).get("source_evidence", [])
    wiki_papers = query_vault_sync(vault_path, section="papers", detail="full").get("sections", {}).get("papers", [])

    matched_source = next((item for item in source_evidence if _matches_existing_item(item, identifiers)), None)
    matched_wiki = [item for item in wiki_papers if _matches_existing_item(item, identifiers)]
    if not matched_source and not matched_wiki:
        return None

    representative = matched_wiki[0] if matched_wiki else matched_source
    return {
        "paper_id": representative.get("paper_id", paper.get("paper_id", "")),
        "title": representative.get("title", paper.get("title", "")),
        "source_evidence_abs_path": _abs_vault_path(
            vault_path,
            (matched_source or {}).get("_path", "") or representative.get("source_evidence_path", ""),
        ),
        "wiki_paper_abs_path": _abs_vault_path(vault_path, matched_wiki[0].get("_path", "")) if matched_wiki else "",
        "wiki_paths": [
            _abs_vault_path(vault_path, item.get("_path", ""))
            for item in matched_wiki
            if item.get("_path")
        ],
        "compiled": bool(matched_wiki),
    }
