"""CrossRef DOI resolution -- resolve a DOI to full bibliographic metadata."""
from __future__ import annotations

import logging
import os
import re
from typing import Any

import httpx

LOG = logging.getLogger(__name__)

CROSSREF_BASE = "https://api.crossref.org/works"


async def resolve_crossref(doi: str) -> dict[str, Any]:
    """Resolve a DOI via CrossRef and return normalised metadata.

    Returns a dict with the standard paper keys.
    Returns an empty dict on failure.
    """
    doi = doi.strip()
    if not doi:
        return {}

    email = os.getenv("OPENALEX_EMAIL", "")
    headers: dict[str, str] = {}
    if email:
        headers["User-Agent"] = f"paper-distill/2.0 (mailto:{email})"

    try:
        async with httpx.AsyncClient(timeout=30.0, headers=headers) as client:
            resp = await client.get(f"{CROSSREF_BASE}/{doi}")
            resp.raise_for_status()
            data = resp.json()
    except (httpx.HTTPStatusError, httpx.RequestError) as exc:
        LOG.warning("CrossRef resolve failed for %s: %s", doi, exc)
        return {}

    item = data.get("message", {})
    if not item:
        return {}

    # Authors
    authors = []
    for author in item.get("author", []):
        given = author.get("given", "")
        family = author.get("family", "")
        if family:
            authors.append(f"{given} {family}".strip())

    # Year -- try multiple date fields
    year = None
    for date_field in ("published-print", "published-online", "created"):
        date_parts = item.get(date_field, {}).get("date-parts", [[]])
        if date_parts and date_parts[0] and date_parts[0][0]:
            year = date_parts[0][0]
            break

    container = item.get("container-title", [])
    venue = container[0] if container else ""

    abstract = item.get("abstract", "")
    if abstract:
        abstract = re.sub(r"<[^>]+>", "", abstract).strip()

    return {
        "title": (item.get("title") or [""])[0],
        "year": year,
        "doi": item.get("DOI", ""),
        "authors": authors,
        "abstract": abstract,
        "source": "crossref",
        "citation_count": item.get("is-referenced-by-count", 0) or 0,
        "open_access_url": "",
        "code_url": "",
        "tldr": "",
        "venue": venue,
    }
