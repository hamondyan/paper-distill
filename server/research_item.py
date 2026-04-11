"""Shared paper entity contract for search, ingest, and wiki writes."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from server.paper_utils import canonical_html_url, canonical_item_url, canonical_pdf_url


@dataclass(frozen=True)
class ResearchItem:
    """Lightweight canonical representation for a paper-like entity."""

    paper_id: str
    citekey: str
    title: str
    authors: list[str] = field(default_factory=list)
    year: int | None = None
    doi: str = ""
    arxiv_id: str = ""
    venue: str = ""
    venue_normalized: str = ""
    venue_tier: str = "unknown"
    venue_source: str = ""
    topic_tags: list[str] = field(default_factory=list)
    canonical_html_url: str = ""
    canonical_pdf_url: str = ""
    canonical_item_url: str = ""

    @classmethod
    def from_search_result(
        cls,
        paper: dict[str, Any],
        *,
        citekey: str,
        topic_tags: list[str] | None = None,
    ) -> "ResearchItem":
        return cls(
            paper_id=str(paper.get("paper_id", "")),
            citekey=citekey,
            title=str(paper.get("title", "")),
            authors=[str(author) for author in paper.get("authors", [])],
            year=paper.get("year"),
            doi=str(paper.get("doi", "")),
            arxiv_id=str(paper.get("arxiv_id", "")),
            venue=str(paper.get("venue_raw") or paper.get("venue", "")),
            venue_normalized=str(paper.get("venue_normalized", "")),
            venue_tier=str(paper.get("venue_tier", "unknown")),
            venue_source=str(paper.get("venue_source", "")),
            topic_tags=list(topic_tags or paper.get("topic_tags", []) or []),
            canonical_html_url=str(paper.get("canonical_html_url") or canonical_html_url(paper)),
            canonical_pdf_url=str(
                paper.get("canonical_pdf_url")
                or paper.get("open_access_url")
                or canonical_pdf_url(paper)
            ),
            canonical_item_url=str(paper.get("canonical_item_url") or canonical_item_url(paper)),
        )

    @classmethod
    def from_inbox_note(cls, note: dict[str, Any], *, citekey: str) -> "ResearchItem":
        return cls.from_search_result(
            note,
            citekey=citekey,
            topic_tags=list(note.get("matched_topics", []) or []),
        )

    def to_source_frontmatter(
        self,
        *,
        source_structured_path: str,
        appendix_policy: str,
        capture_method: str,
        capture_fidelity: str,
        capture_source: str,
        figure_count: int = 0,
        table_count: int = 0,
        equation_count: int = 0,
    ) -> dict[str, Any]:
        return {
            "paper_id": self.paper_id,
            "citekey": self.citekey,
            "title": self.title,
            "authors": list(self.authors),
            "year": self.year,
            "doi": self.doi,
            "arxiv_id": self.arxiv_id,
            "venue": self.venue,
            "venue_normalized": self.venue_normalized,
            "venue_tier": self.venue_tier,
            "venue_source": self.venue_source,
            "topics": list(self.topic_tags),
            "canonical_html_url": self.canonical_html_url,
            "canonical_pdf_url": self.canonical_pdf_url,
            "canonical_item_url": self.canonical_item_url,
            "capture_method": capture_method,
            "capture_fidelity": capture_fidelity,
            "capture_source": capture_source,
            "appendix_policy": appendix_policy,
            "source_structured_path": source_structured_path,
            "figure_count": figure_count,
            "table_count": table_count,
            "equation_count": equation_count,
            "captured_at": datetime.now().isoformat(timespec="seconds"),
            "compiled": False,
        }

    def to_wiki_frontmatter(
        self,
        *,
        source_evidence_path: str,
        source_assets_path: str,
        zotero_mode: str,
        zotero_status: str,
        zotero_import_path: str,
        zotero_uri: str,
        zotero_key: str,
        confidence: float,
        capture_fidelity: str,
        page_state: str = "auto",
        manual_notes_present: bool = False,
    ) -> dict[str, Any]:
        return {
            "paper_id": self.paper_id,
            "citekey": self.citekey,
            "title": self.title,
            "authors": list(self.authors),
            "year": self.year,
            "doi": self.doi,
            "arxiv_id": self.arxiv_id,
            "venue": self.venue,
            "venue_normalized": self.venue_normalized,
            "venue_tier": self.venue_tier,
            "venue_source": self.venue_source,
            "topics": list(self.topic_tags),
            "canonical_html_url": self.canonical_html_url,
            "canonical_pdf_url": self.canonical_pdf_url,
            "canonical_item_url": self.canonical_item_url,
            "source_evidence_path": source_evidence_path,
            "source_assets_path": source_assets_path,
            "zotero_mode": zotero_mode,
            "zotero_status": zotero_status,
            "zotero_import_path": zotero_import_path,
            "zotero_uri": zotero_uri,
            "zotero_key": zotero_key,
            "capture_fidelity": capture_fidelity,
            "page_state": page_state,
            "confidence": float(confidence),
            "last_compiled_at": datetime.now().isoformat(timespec="seconds"),
            "manual_notes_present": bool(manual_notes_present),
            "compiled": True,
            "updated_at": datetime.now().isoformat(timespec="seconds"),
        }
