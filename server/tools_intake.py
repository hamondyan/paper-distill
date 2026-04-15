"""Intake MCP tools — paper discovery, ingestion, and reading.

Registers:
    search-papers    — cross-source academic paper search
    discover_papers  — v3 discovery flow that writes inbox stubs
    ingest_and_read  — approved inbox or direct URL raw-evidence ingest
    read-paper       — read paper metadata and/or full text
"""
from __future__ import annotations

import re
from typing import Any

from fastmcp import FastMCP

from server.server_runtime import (
    search_papers as _search_papers,
    discover_papers_v3 as _discover_papers_v3,
    ingest_and_read_v3 as _ingest_and_read_v3,
    resolve_metadata as _resolve_metadata,
    fetch_pdf_text as _fetch_pdf_text,
)

_DOI_RE = re.compile(r"^10\.\d{4,9}/")
_ARXIV_ID_RE = re.compile(r"^\d{4}\.\d{4,5}(?:v\d+)?$")


# ------------------------------------------------------------------
# Tool 3: search-papers
# ------------------------------------------------------------------

async def search_papers(
    query: str,
    sources: list[str] | None = None,
    max_results: int = 20,
) -> list[dict[str, Any]]:
    """Search academic papers across multiple sources.

    Searches arXiv, Semantic Scholar, OpenAlex, DBLP, and Papers with Code
    in parallel, then deduplicates and merges results.

    Use ``discover_papers`` instead if you also want inbox staging.
    Use this tool when you only want raw search results.

    Args:
        query: Search query string.
        sources: Subset of sources to search (default: all configured).
        max_results: Maximum results per source (default 20).
    """
    return await _search_papers(query=query, sources=sources, max_results=max_results)


# ------------------------------------------------------------------
# Tool 4: discover_papers
# ------------------------------------------------------------------

async def discover_papers(query: str | None = None) -> dict[str, Any]:
    """Run the v3 discovery flow and stage inbox stubs for review."""
    return await _discover_papers_v3(query=query)


# ------------------------------------------------------------------
# Tool 5: ingest_and_read
# ------------------------------------------------------------------

async def ingest_and_read(input_value: str) -> dict[str, Any]:
    """Ingest approved inbox notes or a direct arXiv URL into raw/evidence."""
    return await _ingest_and_read_v3(input_value=input_value)


# ------------------------------------------------------------------
# Tool 6: read-paper
# ------------------------------------------------------------------

async def read_paper(
    identifier: str,
    mode: str = "auto",
    max_pages: int = 10,
) -> dict[str, Any]:
    """Read paper metadata and/or full text from a DOI, arXiv ID, or URL.

    Modes:
    - ``auto`` (default): detects identifier type. DOI → metadata;
      arXiv ID / URL → full text; DOI with open-access → both.
    - ``metadata``: resolve metadata via CrossRef + Unpaywall.
    - ``fulltext``: fetch and extract text (ar5iv HTML or PDF).

    Args:
        identifier: DOI (e.g. "10.48550/arxiv.2410.24164"),
                    arXiv ID (e.g. "2410.24164"), or URL.
        mode: "auto" | "metadata" | "fulltext".
        max_pages: Max PDF pages to extract (default 10).
    """
    identifier = identifier.strip()
    result: dict[str, Any] = {"identifier": identifier, "mode": mode}

    if mode == "metadata":
        meta = await _resolve_metadata(identifier)
        result["metadata"] = meta
        return result

    if mode == "fulltext":
        url = _to_fulltext_url(identifier)
        text = await _fetch_pdf_text(url, max_pages=max_pages)
        result["fulltext"] = text
        return result

    # auto mode
    is_doi = bool(_DOI_RE.match(identifier))
    is_arxiv_id = bool(_ARXIV_ID_RE.match(identifier))

    if is_doi:
        meta = await _resolve_metadata(identifier)
        result["metadata"] = meta
        # If there's an open-access URL, also fetch text
        oa_url = meta.get("open_access_url")
        if oa_url:
            try:
                text = await _fetch_pdf_text(oa_url, max_pages=max_pages)
                result["fulltext"] = text
            except Exception:
                result["fulltext_error"] = "Failed to fetch open-access text"
        return result

    if is_arxiv_id:
        url = f"https://arxiv.org/abs/{identifier}"
        text = await _fetch_pdf_text(url, max_pages=max_pages)
        result["fulltext"] = text
        # Also try to get metadata via DOI
        doi = f"10.48550/arxiv.{identifier}"
        try:
            meta = await _resolve_metadata(doi)
            if meta and not meta.get("error"):
                result["metadata"] = meta
        except Exception:
            pass
        return result

    # Assume URL
    text = await _fetch_pdf_text(identifier, max_pages=max_pages)
    result["fulltext"] = text
    return result


def _to_fulltext_url(identifier: str) -> str:
    """Convert an identifier to a fetchable URL."""
    if _ARXIV_ID_RE.match(identifier):
        return f"https://arxiv.org/abs/{identifier}"
    return identifier


# ------------------------------------------------------------------
# Registration
# ------------------------------------------------------------------

def register_intake_tools(mcp: FastMCP) -> None:
    mcp.tool(name="discover_papers")(discover_papers)
    mcp.tool(name="ingest_and_read")(ingest_and_read)
