"""Data contract helpers for cleaned v3 arXiv captures."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class CleanedArxivDocument:
    title: str
    abstract: str
    markdown: str
    sections: list[dict[str, Any]]
    appendix_snapshot: list[dict[str, str]]
    quality: dict[str, Any]
    figures: list[dict[str, Any]] = field(default_factory=list)
    tables: list[dict[str, Any]] = field(default_factory=list)
    equations: list[dict[str, Any]] = field(default_factory=list)
    capture_fidelity: str = "high"
    capture_source: str = ""
    capture_method: str = ""


def build_cleaned_document(
    *,
    title: str,
    abstract: str,
    markdown: str,
    sections: list[dict[str, Any]],
    appendix_snapshot: list[dict[str, str]],
    quality: dict[str, Any],
    figures: list[dict[str, Any]] | None = None,
    tables: list[dict[str, Any]] | None = None,
    equations: list[dict[str, Any]] | None = None,
    capture_fidelity: str = "high",
    capture_source: str = "",
    capture_method: str = "",
) -> CleanedArxivDocument:
    return CleanedArxivDocument(
        title=title,
        abstract=abstract,
        markdown=markdown,
        sections=sections,
        appendix_snapshot=appendix_snapshot,
        quality=quality,
        figures=list(figures or []),
        tables=list(tables or []),
        equations=list(equations or []),
        capture_fidelity=capture_fidelity,
        capture_source=capture_source,
        capture_method=capture_method,
    )
