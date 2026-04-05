"""arXiv search via the official API."""
from __future__ import annotations

import logging
import re
import xml.etree.ElementTree as ET
from typing import Any

import httpx

LOG = logging.getLogger(__name__)

ARXIV_API = "https://export.arxiv.org/api/query"
ATOM_NS = "{http://www.w3.org/2005/Atom}"


def _parse_entry(entry: ET.Element) -> dict[str, Any]:
    """Parse a single Atom <entry> into normalised paper dict."""
    title = (entry.findtext(f"{ATOM_NS}title") or "").replace("\n", " ").strip()

    # Extract arXiv ID from the entry id URL
    entry_id = entry.findtext(f"{ATOM_NS}id") or ""
    arxiv_id = entry_id.split("/abs/")[-1] if "/abs/" in entry_id else ""
    if arxiv_id and "v" in arxiv_id:
        base, ver = arxiv_id.rsplit("v", 1)
        if ver.isdigit():
            arxiv_id = base

    authors = [
        (a.findtext(f"{ATOM_NS}name") or "").strip()
        for a in entry.findall(f"{ATOM_NS}author")
    ]
    authors = [a for a in authors if a]

    abstract = (entry.findtext(f"{ATOM_NS}summary") or "").replace("\n", " ").strip()

    published = entry.findtext(f"{ATOM_NS}published") or ""
    year = int(published[:4]) if len(published) >= 4 else None

    doi_el = entry.find(f"{{http://arxiv.org/schemas/atom}}doi")
    doi = (doi_el.text or "").strip() if doi_el is not None else ""

    pdf_url = ""
    for link in entry.findall(f"{ATOM_NS}link"):
        if link.get("title") == "pdf":
            pdf_url = link.get("href", "")
            break

    categories = [
        c.get("term", "")
        for c in entry.findall(f"{{http://arxiv.org/schemas/atom}}category")
        if c.get("term")
    ]

    return {
        "title": title,
        "year": year,
        "doi": doi,
        "arxiv_id": arxiv_id,
        "authors": authors,
        "abstract": abstract,
        "source": "arxiv",
        "citation_count": None,
        "open_access_url": pdf_url,
        "html_url": f"https://ar5iv.labs.arxiv.org/html/{arxiv_id}" if arxiv_id else "",
        "code_url": "",
        "tldr": "",
        "venue": "",
        "arxiv_categories": categories,
        "published": published,
    }


async def search_arxiv(query: str, max_results: int = 20) -> list[dict]:
    """Search arXiv for papers matching *query*. Returns normalised dicts."""
    return await search_arxiv_query(
        f'all:"{query}"',
        max_results=max_results,
        sort_by="relevance",
    )


async def search_arxiv_query(
    search_query: str,
    max_results: int = 20,
    sort_by: str = "relevance",
) -> list[dict]:
    """Search arXiv using a raw API search query."""
    params = {
        "search_query": search_query,
        "start": 0,
        "max_results": min(max_results, 100),
        "sortBy": sort_by,
        "sortOrder": "descending",
    }

    try:
        async with httpx.AsyncClient(timeout=30.0, follow_redirects=True) as client:
            resp = await client.get(ARXIV_API, params=params)
            resp.raise_for_status()
    except (httpx.HTTPStatusError, httpx.RequestError) as exc:
        LOG.warning("arXiv search failed: %s", exc)
        return []

    try:
        root = ET.fromstring(resp.text)
    except ET.ParseError as exc:
        LOG.warning("arXiv XML parse error: %s", exc)
        return []

    entries = root.findall(f"{ATOM_NS}entry")
    return [_parse_entry(e) for e in entries[:max_results]]


async def fetch_arxiv_record(arxiv_id: str) -> dict[str, Any] | None:
    """Fetch one canonical arXiv record by identifier."""
    normalized = (arxiv_id or "").strip()
    if not normalized:
        return None

    params = {"id_list": normalized}
    try:
        async with httpx.AsyncClient(timeout=30.0, follow_redirects=True) as client:
            resp = await client.get(ARXIV_API, params=params)
            resp.raise_for_status()
    except (httpx.HTTPStatusError, httpx.RequestError) as exc:
        LOG.warning("arXiv record fetch failed for %s: %s", normalized, exc)
        return None

    try:
        root = ET.fromstring(resp.text)
    except ET.ParseError as exc:
        LOG.warning("arXiv XML parse error for %s: %s", normalized, exc)
        return None

    entries = root.findall(f"{ATOM_NS}entry")
    if not entries:
        return None
    return _parse_entry(entries[0])


def _escape_query_value(value: str) -> str:
    collapsed = " ".join((value or "").split())
    return re.sub(r'"', "", collapsed)


async def search_arxiv_title_author(
    title: str,
    first_author: str,
    max_results: int = 10,
) -> list[dict]:
    """Search arXiv for papers by title and first-author surname."""
    title_value = _escape_query_value(title)
    author_value = _escape_query_value(first_author)

    if title_value and author_value:
        query = f'ti:"{title_value}" AND au:"{author_value}"'
    elif title_value:
        query = f'ti:"{title_value}"'
    elif author_value:
        query = f'au:"{author_value}"'
    else:
        return []

    return await search_arxiv_query(query, max_results=max_results, sort_by="relevance")
