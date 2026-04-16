from __future__ import annotations

import asyncio
import unittest
from unittest.mock import AsyncMock, patch

from server.arxiv_html_fetch import fetch_arxiv_html


class ArxivHtmlFetchTest(unittest.TestCase):
    def test_fetch_prefers_native_html(self) -> None:
        async def run() -> tuple[str, str]:
            with patch("server.arxiv_html_fetch._fetch_html", new=AsyncMock(return_value="<article></article>")):
                return await fetch_arxiv_html("2501.00001")

        html, source = asyncio.run(run())

        self.assertEqual(html, "<article></article>")
        self.assertEqual(source, "arxiv_native_html")

    def test_fetch_tries_ar5iv_when_native_has_no_html(self) -> None:
        async def fake_fetch(url: str, timeout: float = 30.0) -> str:
            if url.startswith("https://arxiv.org/html/"):
                raise RuntimeError("This paper does not have an HTML version available on arXiv.")
            return "<article>ar5iv</article>"

        async def run() -> tuple[str, str]:
            with patch("server.arxiv_html_fetch._fetch_html", new=fake_fetch):
                return await fetch_arxiv_html("2501.00001")

        html, source = asyncio.run(run())

        self.assertEqual(html, "<article>ar5iv</article>")
        self.assertEqual(source, "ar5iv_html")
