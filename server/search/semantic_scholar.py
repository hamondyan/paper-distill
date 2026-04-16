"""Semantic Scholar search via the public Graph API."""
from __future__ import annotations

import logging
from typing import Any

import httpx

from server.config import get_search_settings

LOG = logging.getLogger(__name__)

S2_BASE = "https://api.semanticscholar.org/graph/v1/paper/search"
S2_FIELDS = (
    "title,abstract,tldr,citationCount,year,authors,"
    "venue,externalIds,openAccessPdf"
)


def _normalise(paper: dict[str, Any]) -> dict[str, Any]:
    ext = paper.get("externalIds") or {}
    authors = [
        a.get("name", "")
        for a in (paper.get("authors") or [])
        if a.get("name")
    ]

    tldr_obj = paper.get("tldr") or {}
    tldr = tldr_obj.get("text", "") if isinstance(tldr_obj, dict) else ""

    oa_pdf = paper.get("openAccessPdf") or {}
    oa_url = oa_pdf.get("url", "") if isinstance(oa_pdf, dict) else ""

    return {
        "title": paper.get("title", ""),
        "year": paper.get("year"),
        "doi": ext.get("DOI", ""),
        "authors": authors,
        "abstract": paper.get("abstract", "") or "",
        "source": "s2",
        "citation_count": paper.get("citationCount", 0) or 0,
        "open_access_url": oa_url,
        "code_url": "",
        "tldr": tldr,
        "venue": paper.get("venue", "") or "",
    }


async def search_semantic_scholar(query: str, max_results: int = 20) -> list[dict]:
    """Search Semantic Scholar for papers matching *query*."""
    api_key = get_search_settings()["semantic_scholar_api_key"]
    headers: dict[str, str] = {}
    if api_key:
        headers["x-api-key"] = api_key

    params = {
        "query": query,
        "fields": S2_FIELDS,
        "limit": min(max_results, 100),
    }

    try:
        async with httpx.AsyncClient(timeout=30.0, headers=headers) as client:
            resp = await client.get(S2_BASE, params=params)
            resp.raise_for_status()
            data = resp.json()
    except (httpx.HTTPStatusError, httpx.RequestError) as exc:
        LOG.warning("Semantic Scholar search failed: %s", exc)
        return []

    return [_normalise(p) for p in data.get("data", [])[:max_results]]
