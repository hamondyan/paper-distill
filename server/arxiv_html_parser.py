"""Lightweight HTML parser helpers for arXiv capture."""
from __future__ import annotations

import re
from dataclasses import dataclass

from bs4 import BeautifulSoup, Tag


_TEXT_COLLAPSE_RE = re.compile(r"\s+")
_CITATION_NOISE_RE = re.compile(r"\s*\[[^\]]+\]")


def _collapse_ws(text: str) -> str:
    return _TEXT_COLLAPSE_RE.sub(" ", text or "").strip()


def _clean_text(text: str) -> str:
    text = _collapse_ws(text)
    text = _CITATION_NOISE_RE.sub("", text)
    return _collapse_ws(text)


def _heading_text(node: Tag) -> str:
    return _clean_text(node.get_text(" ", strip=True))


def _extract_title(article: Tag) -> str:
    node = article.select_one("h1.ltx_title_document")
    if not isinstance(node, Tag):
        return ""
    for tag in node.select(".ltx_tag"):
        tag.decompose()
    return _heading_text(node)


def _extract_abstract(article: Tag) -> str:
    block = article.select_one(".ltx_abstract")
    if not isinstance(block, Tag):
        return ""
    clone = BeautifulSoup(str(block), "html.parser")
    for tag in clone.select(".ltx_title, .ltx_tag, .ltx_note_mark"):
        tag.decompose()
    return _clean_text(clone.get_text(" ", strip=True))


@dataclass
class ParsedArxivHtml:
    article: Tag
    title: str
    abstract: str


def parse_arxiv_html_document(html: str) -> ParsedArxivHtml:
    soup = BeautifulSoup(html, "html.parser")
    article = soup.select_one("article.ltx_document") or soup.find("article")
    if not isinstance(article, Tag):
        raise ValueError("ar5iv article node not found")
    return ParsedArxivHtml(
        article=article,
        title=_extract_title(article),
        abstract=_extract_abstract(article),
    )
