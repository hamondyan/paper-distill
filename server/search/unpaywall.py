"""Unpaywall DOI lookup -- find open-access PDF links for a given DOI."""
from __future__ import annotations

import logging
import os
from typing import Any

import httpx

LOG = logging.getLogger(__name__)

UNPAYWALL_BASE = "https://api.unpaywall.org/v2"


async def lookup_unpaywall(doi: str) -> dict[str, Any]:
    """Look up a DOI on Unpaywall and return OA metadata.

    Returns a dict with keys:
        doi, is_oa, best_oa_url, oa_status, journal, publisher
    Returns an empty dict on failure.
    """
    email = os.getenv("UNPAYWALL_EMAIL") or os.getenv("OPENALEX_EMAIL", "")
    if not email:
        LOG.warning("No email set for Unpaywall (set UNPAYWALL_EMAIL or OPENALEX_EMAIL)")
        return {}

    doi = doi.strip()
    if not doi:
        return {}

    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.get(
                f"{UNPAYWALL_BASE}/{doi}",
                params={"email": email},
            )
            if resp.status_code != 200:
                LOG.warning("Unpaywall returned %d for DOI %s", resp.status_code, doi)
                return {}
            data = resp.json()
    except (httpx.HTTPStatusError, httpx.RequestError) as exc:
        LOG.warning("Unpaywall lookup failed for %s: %s", doi, exc)
        return {}

    best = data.get("best_oa_location") or {}
    best_url = best.get("url_for_pdf") or best.get("url") or ""

    return {
        "doi": doi,
        "is_oa": data.get("is_oa", False),
        "best_oa_url": best_url,
        "oa_status": data.get("oa_status", ""),
        "journal": data.get("journal_name", ""),
        "publisher": data.get("publisher", ""),
    }
