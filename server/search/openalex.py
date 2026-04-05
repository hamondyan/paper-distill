"""OpenAlex search via the public /works endpoint."""
from __future__ import annotations

import logging
import os
from typing import Any

import httpx

LOG = logging.getLogger(__name__)

OPENALEX_BASE = "https://api.openalex.org/works"


def _reconstruct_abstract(inverted_index: dict[str, list[int]]) -> str:
    """Rebuild abstract text from OpenAlex inverted index format."""
    if not inverted_index:
        return ""
    positions: list[tuple[int, str]] = []
    for word, idxs in inverted_index.items():
        for pos in idxs:
            positions.append((pos, word))
    positions.sort(key=lambda x: x[0])
    return " ".join(w for _, w in positions)


def _normalise(work: dict[str, Any]) -> dict[str, Any]:
    authors = [
        a.get("author", {}).get("display_name", "")
        for a in (work.get("authorships") or [])
    ]
    authors = [a for a in authors if a]

    oa = work.get("open_access") or {}
    oa_url = oa.get("oa_url") or ""
    if not oa_url:
        loc = work.get("primary_location") or {}
        oa_url = loc.get("pdf_url") or ""

    abstract = _reconstruct_abstract(work.get("abstract_inverted_index") or {})

    doi_raw = work.get("doi") or ""
    doi = doi_raw.replace("https://doi.org/", "") if doi_raw else ""

    venue = ""
    loc = work.get("primary_location") or {}
    src = loc.get("source") or {}
    venue = src.get("display_name", "")

    return {
        "title": work.get("title", "") or "",
        "year": work.get("publication_year"),
        "doi": doi,
        "authors": authors,
        "abstract": abstract,
        "source": "openalex",
        "citation_count": work.get("cited_by_count", 0) or 0,
        "open_access_url": oa_url,
        "code_url": "",
        "tldr": "",
        "venue": venue,
    }


async def search_openalex(query: str, max_results: int = 20) -> list[dict]:
    """Search OpenAlex for papers matching *query*."""
    email = os.getenv("OPENALEX_EMAIL", "")
    params: dict[str, Any] = {
        "search": query,
        "per_page": min(max_results, 50),
        "sort": "relevance_score:desc",
    }
    if email:
        params["mailto"] = email

    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.get(OPENALEX_BASE, params=params)
            resp.raise_for_status()
            data = resp.json()
    except (httpx.HTTPStatusError, httpx.RequestError) as exc:
        LOG.warning("OpenAlex search failed: %s", exc)
        return []

    return [_normalise(w) for w in data.get("results", [])[:max_results]]
