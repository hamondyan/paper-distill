"""DBLP search via the public publication search API."""
from __future__ import annotations

import logging
from typing import Any

import httpx

LOG = logging.getLogger(__name__)

DBLP_BASE = "https://dblp.org/search/publ/api"


def _normalise(hit: dict[str, Any]) -> dict[str, Any]:
    info = hit.get("info", {})

    # Authors: can be string, dict, or list
    authors_raw = info.get("authors", {}).get("author", [])
    if isinstance(authors_raw, str):
        authors = [authors_raw]
    elif isinstance(authors_raw, dict):
        authors = [authors_raw.get("text", authors_raw.get("@text", ""))]
    elif isinstance(authors_raw, list):
        authors = []
        for a in authors_raw:
            if isinstance(a, str):
                authors.append(a)
            elif isinstance(a, dict):
                authors.append(a.get("text", a.get("@text", "")))
    else:
        authors = []
    authors = [a for a in authors if a]

    year = None
    year_str = info.get("year")
    if year_str:
        try:
            year = int(year_str)
        except (ValueError, TypeError):
            pass

    doi = info.get("doi", "") or ""
    if doi and not doi.startswith("10."):
        doi = ""

    ee = info.get("ee", "")
    if isinstance(ee, list):
        ee = ee[0] if ee else ""

    venue = info.get("venue", "")
    if isinstance(venue, list):
        venue = ", ".join(venue)

    title = info.get("title", "")
    if title.endswith("."):
        title = title[:-1]

    return {
        "title": title,
        "year": year,
        "doi": doi,
        "authors": authors,
        "abstract": "",  # DBLP does not provide abstracts
        "source": "dblp",
        "citation_count": None,
        "open_access_url": ee,
        "code_url": "",
        "tldr": "",
        "venue": venue,
    }


async def search_dblp(query: str, max_results: int = 20) -> list[dict]:
    """Search DBLP for papers matching *query*."""
    params = {
        "q": query,
        "format": "json",
        "h": min(max_results, 40),
    }

    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.get(DBLP_BASE, params=params)
            resp.raise_for_status()
            data = resp.json()
    except (httpx.HTTPStatusError, httpx.RequestError) as exc:
        LOG.warning("DBLP search failed: %s", exc)
        return []

    hits = data.get("result", {}).get("hits", {}).get("hit", [])
    return [_normalise(h) for h in hits[:max_results]]
