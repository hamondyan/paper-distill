"""Helpers for fetching arXiv HTML with a native->ar5iv fallback."""
from __future__ import annotations

import httpx


_NATIVE_NO_HTML_MARKERS = (
    "does not have an html version",
    "404",
)


async def _fetch_html(url: str, timeout: float = 30.0) -> str:
    async with httpx.AsyncClient(timeout=timeout, follow_redirects=True) as client:
        response = await client.get(url)
        if response.status_code == 404:
            raise RuntimeError(
                "This paper does not have an HTML version available on arXiv. "
                "Older papers may only be available as PDF."
            )
        response.raise_for_status()
        return response.text


def _should_fallback_to_ar5iv(exc: Exception) -> bool:
    message = str(exc).lower()
    return any(marker in message for marker in _NATIVE_NO_HTML_MARKERS)


async def fetch_arxiv_html_with_fallback(arxiv_id: str, timeout: float = 30.0) -> tuple[str, str]:
    native_url = f"https://arxiv.org/html/{arxiv_id}"
    ar5iv_url = f"https://ar5iv.labs.arxiv.org/html/{arxiv_id}"
    try:
        return await _fetch_html(native_url, timeout=timeout), "arxiv_native_html"
    except Exception as exc:
        if not _should_fallback_to_ar5iv(exc):
            raise
    return await _fetch_html(ar5iv_url, timeout=timeout), "ar5iv_html"
