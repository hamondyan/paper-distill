"""Papers With Code search via the public API."""
from __future__ import annotations

import logging
from typing import Any

import httpx

LOG = logging.getLogger(__name__)

PWC_BASE = "https://paperswithcode.com/api/v1"


def _normalise(paper: dict[str, Any]) -> dict[str, Any]:
    title = paper.get("title", "")
    abstract = paper.get("abstract", "") or ""
    arxiv_id = paper.get("arxiv_id", "") or ""
    url_pdf = paper.get("url_pdf", "") or ""
    published = paper.get("published", "") or ""

    year = None
    if published and len(published) >= 4:
        try:
            year = int(published[:4])
        except ValueError:
            pass

    raw_authors = paper.get("authors", []) or []
    authors: list[str] = []
    for a in raw_authors:
        if isinstance(a, dict):
            name = a.get("name", "")
        elif isinstance(a, str):
            name = a
        else:
            name = ""
        if name:
            authors.append(name)

    doi = ""
    if arxiv_id:
        doi = ""  # arXiv papers rarely have DOIs in PWC data

    return {
        "title": title,
        "year": year,
        "doi": doi,
        "arxiv_id": arxiv_id,
        "authors": authors,
        "abstract": abstract,
        "source": "pwc",
        "citation_count": None,
        "open_access_url": url_pdf,
        "code_url": "",
        "tldr": "",
        "venue": "",
        "published": published,
    }


def _normalise_search_result(item: dict[str, Any]) -> dict[str, Any] | None:
    """Normalise a search endpoint result (wraps paper in a 'paper' key)."""
    paper = item.get("paper", {})
    if not paper:
        return None
    return {
        "title": paper.get("title", ""),
        "year": None,
        "doi": "",
        "arxiv_id": paper.get("arxiv_id", "") or "",
        "authors": [],
        "abstract": (paper.get("abstract") or "")[:500],
        "source": "pwc",
        "citation_count": None,
        "open_access_url": paper.get("url_pdf", "") or "",
        "code_url": "",
        "tldr": "",
        "venue": "",
    }


async def search_papers_with_code(query: str, max_results: int = 20) -> list[dict]:
    """Search Papers With Code for papers matching *query*."""
    params = {
        "q": query,
        "page": 1,
        "items_per_page": min(max_results, 50),
    }

    try:
        async with httpx.AsyncClient(timeout=30.0, follow_redirects=True) as client:
            resp = await client.get(f"{PWC_BASE}/search/", params=params)
            resp.raise_for_status()
            data = resp.json()
    except (httpx.HTTPStatusError, httpx.RequestError) as exc:
        LOG.warning("Papers With Code search failed: %s", exc)
        return []

    papers = []
    for item in data.get("results", []):
        p = _normalise_search_result(item)
        if p:
            papers.append(p)
    return papers[:max_results]
