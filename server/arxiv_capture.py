"""arXiv binding, ar5iv capture, and CRGP-DNL note generation."""
from __future__ import annotations

import asyncio
import re
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Any

import httpx
from bs4 import BeautifulSoup, Tag
from rapidfuzz import fuzz

from server.paper_utils import (
    canonical_html_url,
    canonical_item_url,
    canonical_pdf_url,
    first_author_surname,
    normalise_title,
    paper_arxiv_id,
    paper_id,
)
from server.search import search_arxiv_title_author


_HEADING_LEVELS = {
    "h2": 2,
    "h3": 3,
    "h4": 4,
}
_TEXT_COLLAPSE_RE = re.compile(r"\s+")
_CITATION_NOISE_RE = re.compile(r"\s*\[[^\]]+\]")
_SECTION_KEYWORDS = {
    "related": ("related work", "background", "preliminar", "prior work"),
    "proposal": ("method", "approach", "framework", "model", "architecture", "policy"),
    "results": ("experiment", "evaluation", "result", "analysis", "benchmark"),
    "discussion": ("discussion", "conclusion", "limitations", "future work"),
}
_BIND_COPY_FIELDS = (
    "doi",
    "year",
    "authors",
    "abstract",
    "published",
    "source",
    "open_access_url",
    "html_url",
    "title",
)


def _collapse_ws(text: str) -> str:
    return _TEXT_COLLAPSE_RE.sub(" ", text or "").strip()


def _clean_text(text: str) -> str:
    text = _collapse_ws(text)
    text = _CITATION_NOISE_RE.sub("", text)
    return _collapse_ws(text)


def _title_similarity(a: str, b: str) -> float:
    norm_a = normalise_title(a)
    norm_b = normalise_title(b)
    if not norm_a or not norm_b:
        return 0.0
    if norm_a == norm_b:
        return 1.0
    return fuzz.ratio(norm_a, norm_b) / 100.0


def _year_distance(a: Any, b: Any) -> int:
    try:
        year_a = int(str(a)[:4])
        year_b = int(str(b)[:4])
    except (TypeError, ValueError):
        return 9_999
    return abs(year_a - year_b)


def _annotate_bound_candidate(candidate: dict[str, Any]) -> dict[str, Any]:
    candidate["arxiv_id"] = paper_arxiv_id(candidate)
    candidate["paper_id"] = paper_id(candidate)
    candidate["canonical_html_url"] = canonical_html_url(candidate)
    candidate["canonical_pdf_url"] = canonical_pdf_url(candidate)
    candidate["canonical_item_url"] = canonical_item_url(candidate)
    candidate["arxiv_binding_status"] = "matched"
    return candidate


def _binding_score(
    target_title: str,
    target_surname: str,
    target_year: Any,
    match: dict[str, Any],
    similarity_threshold: float,
) -> tuple[int, int, int, int] | None:
    match_title = str(match.get("title", "")).strip()
    exact_title = normalise_title(match_title) == target_title
    similarity = _title_similarity(target_title, match_title)
    match_surname = first_author_surname(match)
    surname_matches = target_surname == match_surname
    if not exact_title and similarity < similarity_threshold:
        return None
    if not surname_matches:
        return None
    return (
        1 if exact_title else 0,
        1 if surname_matches else 0,
        -_year_distance(target_year, match.get("year")),
        1 if canonical_html_url(match) else 0,
    )


async def bind_paper_to_arxiv(
    paper: dict[str, Any],
    similarity_threshold: float = 0.92,
) -> dict[str, Any] | None:
    """Bind a discovered paper to a canonical arXiv record or return ``None``."""
    candidate = dict(paper)
    arxiv_id = paper_arxiv_id(candidate)
    if arxiv_id:
        candidate["arxiv_id"] = arxiv_id
        return _annotate_bound_candidate(candidate)

    title = str(candidate.get("title", "")).strip()
    if not title:
        return None

    surname = first_author_surname(candidate)
    if not surname:
        return None
    results = await search_arxiv_title_author(title, surname, max_results=10)
    if not results:
        return None

    target_title = normalise_title(title)
    target_surname = surname
    target_year = candidate.get("year")
    scored_matches: list[tuple[tuple[int, int, int, int], dict[str, Any]]] = []

    for match in results:
        score = _binding_score(
            target_title,
            target_surname,
            target_year,
            match,
            similarity_threshold,
        )
        if score is None:
            continue
        scored_matches.append((score, match))

    if not scored_matches:
        return None

    scored_matches.sort(key=lambda item: item[0], reverse=True)
    best = dict(scored_matches[0][1])
    for field in _BIND_COPY_FIELDS:
        if best.get(field) and not candidate.get(field):
            candidate[field] = best[field]

    candidate["arxiv_id"] = best.get("arxiv_id") or paper_arxiv_id(best)
    return _annotate_bound_candidate(candidate)


def _has_ancestor_with_class(node: Tag, class_fragment: str) -> bool:
    current: Tag | None = node
    while current is not None:
        classes = current.get("class", [])
        if any(class_fragment in cls for cls in classes):
            return True
        current = current.parent if isinstance(current.parent, Tag) else None
    return False


def _heading_text(node: Tag) -> str:
    return _clean_text(node.get_text(" ", strip=True))


def _extract_title(article: Tag) -> str:
    node = article.select_one("h1.ltx_title_document")
    if not node:
        return ""
    for tag in node.select(".ltx_tag"):
        tag.decompose()
    return _heading_text(node)


def _extract_abstract(article: Tag) -> str:
    block = article.select_one(".ltx_abstract")
    if not block:
        return ""
    clone = BeautifulSoup(str(block), "html.parser")
    for tag in clone.select(".ltx_title, .ltx_tag, .ltx_note_mark"):
        tag.decompose()
    return _clean_text(clone.get_text(" ", strip=True))


def _preclean_article(article: Tag, preserve_math: bool = True) -> tuple[int, int]:
    """Strip noise in-place and return (bibliography_chars, appendix_chars)."""
    bibliography_chars = 0
    appendix_chars = 0
    removable = "script, style, nav, footer, svg"
    if not preserve_math:
        removable += ", math"
    for tag in article.select(removable):
        tag.decompose()
    for tag in article.select(".ltx_page_footer, .ltx_page_header, .ltx_note_mark, .ltx_role_footnote"):
        tag.decompose()
    for tag in article.select(".ltx_bibliography, .ltx_toclist, .ltx_ref"):
        if getattr(tag, "attrs", None) is None:
            continue
        text = _clean_text(tag.get_text(" ", strip=True))
        classes = tag.get("class") or []
        if "ltx_bibliography" in " ".join(classes):
            bibliography_chars += len(text)
        tag.decompose()
    for tag in article.select(".ltx_tag_equation"):
        tag.decompose()
    for appendix in article.select("section.ltx_appendix"):
        appendix_chars += len(_clean_text(appendix.get_text(" ", strip=True)))
    return bibliography_chars, appendix_chars


def _section_heading_for_node(node: Tag) -> str:
    for heading in node.find_all_previous(["h2", "h3", "h4"]):
        text = _heading_text(heading)
        if not text or text.lower() == "abstract":
            continue
        if re.search(r"\b(reference|bibliography)\b", text, re.IGNORECASE):
            continue
        return text
    return "Document Body"


def _is_appendix_heading(heading: str) -> bool:
    return "appendix" in heading.lower()


def _label_from_caption(caption: str, prefix: str, fallback_index: int) -> str:
    pattern = rf"\b({prefix}\s*[A-Za-z0-9.\-]+)"
    match = re.search(pattern, caption, re.IGNORECASE)
    if match:
        return match.group(1).replace("Fig.", "Figure")
    return f"{prefix} {fallback_index}"


def _math_text(node: Tag) -> str:
    for attr in ("alttext", "aria-label", "data-mathml"):
        value = str(node.get(attr, "")).strip()
        if value:
            return _collapse_ws(value)
    annotation = node.select_one("annotation[encoding*='tex'], annotation[encoding*='latex']")
    if isinstance(annotation, Tag):
        text = annotation.get_text(" ", strip=True)
        if text:
            return _collapse_ws(text)
    text = node.get_text(" ", strip=True)
    return _collapse_ws(text)


def _table_markdown(rows: list[list[str]]) -> str:
    if not rows:
        return ""
    width = max(len(row) for row in rows)
    normalized = [row + [""] * (width - len(row)) for row in rows]
    header = normalized[0]
    lines = [
        f"| {' | '.join(header)} |",
        f"| {' | '.join(['---'] * width)} |",
    ]
    for row in normalized[1:]:
        lines.append(f"| {' | '.join(row)} |")
    return "\n".join(lines)


def _table_summary(rows: list[list[str]], caption: str) -> str:
    if caption:
        return caption
    if not rows:
        return "Structured table detected."
    header = ", ".join(cell for cell in rows[0] if cell) or "unnamed columns"
    first_row = ", ".join(cell for cell in rows[1] if cell) if len(rows) > 1 else ""
    if first_row:
        return f"Columns: {header}. First data row: {first_row}."
    return f"Columns: {header}."


def _extract_figures(
    article: Tag,
    *,
    appendix_policy: str,
    preserve_figures: bool,
    max_figures: int,
) -> list[dict[str, Any]]:
    if not preserve_figures or max_figures <= 0:
        return []
    figures: list[dict[str, Any]] = []
    for figure in article.find_all("figure"):
        if len(figures) >= max_figures:
            break
        if _has_ancestor_with_class(figure, "ltx_bibliography"):
            continue
        section_heading = _section_heading_for_node(figure)
        if appendix_policy == "summary_only" and _is_appendix_heading(section_heading):
            continue
        caption_node = figure.find("figcaption")
        caption = _clean_text(caption_node.get_text(" ", strip=True)) if isinstance(caption_node, Tag) else ""
        if figure.find("table") is not None or caption.lower().startswith("table "):
            continue
        image = figure.find("img")
        image_url = ""
        alt_text = ""
        if isinstance(image, Tag):
            image_url = str(image.get("src") or image.get("data-src") or "").strip()
            alt_text = _clean_text(str(image.get("alt", "")))
        if not caption and not image_url:
            continue
        figures.append(
            {
                "label": _label_from_caption(caption, "Figure", len(figures) + 1),
                "caption": caption or "Figure detected without a stable caption.",
                "section": section_heading,
                "image_url": image_url,
                "alt_text": alt_text,
            }
        )
    return figures


def _extract_tables(
    article: Tag,
    *,
    appendix_policy: str,
    preserve_tables: bool,
    max_tables: int,
) -> list[dict[str, Any]]:
    if not preserve_tables or max_tables <= 0:
        return []
    tables: list[dict[str, Any]] = []
    for table in article.find_all("table"):
        if len(tables) >= max_tables:
            break
        if _has_ancestor_with_class(table, "ltx_bibliography"):
            continue
        if _has_ancestor_with_class(table, "ltx_eqn") or _has_ancestor_with_class(table, "ltx_equation"):
            continue
        table_classes = " ".join(table.get("class", [])).lower()
        if "eqn" in table_classes or "equation" in table_classes:
            continue
        section_heading = _section_heading_for_node(table)
        if appendix_policy == "summary_only" and _is_appendix_heading(section_heading):
            continue
        rows: list[list[str]] = []
        for tr in table.find_all("tr"):
            cells = [_clean_text(cell.get_text(" ", strip=True)) for cell in tr.find_all(["th", "td"])]
            cells = [cell for cell in cells if cell]
            if cells:
                rows.append(cells)
        if not rows:
            continue
        figure_parent = table.find_parent("figure")
        figure_classes = " ".join(figure_parent.get("class", [])).lower() if isinstance(figure_parent, Tag) else ""
        if "ltx_tabular" not in table_classes and "ltx_table" not in figure_classes:
            continue
        caption_node = figure_parent.find("figcaption") if isinstance(figure_parent, Tag) else None
        caption = _clean_text(caption_node.get_text(" ", strip=True)) if isinstance(caption_node, Tag) else ""
        tables.append(
            {
                "label": _label_from_caption(caption, "Table", len(tables) + 1),
                "caption": caption,
                "section": section_heading,
                "summary": _table_summary(rows, caption),
                "markdown": _table_markdown(rows[:12]),
                "row_count": len(rows),
                "column_count": max(len(row) for row in rows),
            }
        )
    return tables


def _extract_equations(
    article: Tag,
    *,
    appendix_policy: str,
    preserve_math: bool,
    max_equations: int,
) -> list[dict[str, Any]]:
    if not preserve_math or max_equations <= 0:
        return []
    equations: list[dict[str, Any]] = []
    seen: set[int] = set()
    candidates = article.select(".ltx_equation, .ltx_equationgroup, math[display='block'], .ltx_eqn_table")
    for node in candidates:
        if len(equations) >= max_equations:
            break
        if not isinstance(node, Tag):
            continue
        if id(node) in seen:
            continue
        if node.name == "math" and _has_ancestor_with_class(node, "ltx_equation"):
            continue
        section_heading = _section_heading_for_node(node)
        if appendix_policy == "summary_only" and _is_appendix_heading(section_heading):
            continue
        math_node = node if node.name == "math" else node.find("math")
        target = math_node if isinstance(math_node, Tag) else node
        text = _math_text(target)
        if len(text) < 3:
            continue
        equations.append(
            {
                "label": f"Equation E{len(equations) + 1}",
                "section": section_heading,
                "text": text,
            }
        )
        seen.add(id(node))
    return equations


@dataclass
class CleanedArxivDocument:
    title: str
    abstract: str
    markdown: str
    sections: list[dict[str, Any]]
    appendix_snapshot: list[dict[str, str]]
    quality: dict[str, Any]
    figures: list[dict[str, Any]] = field(default_factory=list)
    tables: list[dict[str, Any]] = field(default_factory=list)
    equations: list[dict[str, Any]] = field(default_factory=list)
    capture_fidelity: str = "high"


def clean_ar5iv_html(
    html: str,
    appendix_policy: str = "summary_only",
    min_body_chars: int = 1500,
    preserve_math: bool = True,
    preserve_figures: bool = True,
    preserve_tables: bool = True,
    max_figures: int = 12,
    max_tables: int = 12,
    max_equations: int = 24,
) -> CleanedArxivDocument:
    """Convert ar5iv HTML into cleaned markdown plus structured section data."""
    soup = BeautifulSoup(html, "html.parser")
    article = soup.select_one("article.ltx_document") or soup.find("article")
    if not isinstance(article, Tag):
        raise ValueError("ar5iv article node not found")

    title = _extract_title(article)
    abstract = _extract_abstract(article)
    bibliography_chars, appendix_chars = _preclean_article(article, preserve_math=preserve_math)
    figures = _extract_figures(
        article,
        appendix_policy=appendix_policy,
        preserve_figures=preserve_figures,
        max_figures=max_figures,
    )
    tables = _extract_tables(
        article,
        appendix_policy=appendix_policy,
        preserve_tables=preserve_tables,
        max_tables=max_tables,
    )
    equations = _extract_equations(
        article,
        appendix_policy=appendix_policy,
        preserve_math=preserve_math,
        max_equations=max_equations,
    )

    body_blocks: list[str] = []
    sections: list[dict[str, Any]] = []
    current_section: dict[str, Any] | None = None
    appendix_snapshot: list[dict[str, str]] = []
    in_appendix = False
    current_appendix: dict[str, str] | None = None

    def ensure_section(heading: str, level: int) -> dict[str, Any]:
        nonlocal current_section
        section = {"heading": heading, "level": level, "paragraphs": [], "captions": []}
        sections.append(section)
        current_section = section
        return section

    for node in article.find_all(["h2", "h3", "h4", "p", "figcaption"], recursive=True):
        if not isinstance(node, Tag):
            continue
        if node.name == "p" and _has_ancestor_with_class(node, "ltx_abstract"):
            continue
        if _has_ancestor_with_class(node, "ltx_bibliography"):
            continue

        if node.name in _HEADING_LEVELS:
            text = _heading_text(node)
            if not text or text.lower() == "abstract":
                continue
            if re.search(r"\b(reference|bibliography)\b", text, re.IGNORECASE):
                break
            level = _HEADING_LEVELS[node.name]
            if appendix_policy == "summary_only" and "appendix" in text.lower():
                in_appendix = True
                current_appendix = {"heading": text, "summary": ""}
                appendix_snapshot.append(current_appendix)
                continue
            if in_appendix and appendix_policy == "summary_only":
                current_appendix = {"heading": text, "summary": ""}
                appendix_snapshot.append(current_appendix)
                continue
            body_blocks.append(f"{'#' * level} {text}")
            ensure_section(text, level)
            continue

        text = _clean_text(node.get_text(" ", strip=True))
        if len(text) < 20:
            continue

        if in_appendix and appendix_policy == "summary_only":
            if current_appendix and not current_appendix["summary"] and node.name == "p":
                current_appendix["summary"] = text
            continue

        if node.name == "figcaption":
            body_blocks.append(f"> Caption: {text}")
            if current_section is not None:
                current_section["captions"].append(text)
            continue

        body_blocks.append(text)
        if current_section is None:
            current_section = ensure_section("Document Body", 2)
        current_section["paragraphs"].append(text)

    main_body_chars = sum(len(block) for block in body_blocks)
    bibliography_ratio = bibliography_chars / max(main_body_chars + bibliography_chars, 1)
    has_structured_body = bool(abstract) or sum(1 for section in sections if section["level"] <= 3) >= 2
    if not title:
        raise ValueError("cleaner could not identify document title")
    if not has_structured_body:
        raise ValueError("cleaner could not identify abstract or section structure")
    if main_body_chars < min_body_chars:
        raise ValueError(f"cleaned body too short ({main_body_chars} chars)")
    if bibliography_ratio > 0.45:
        raise ValueError(f"bibliography ratio too high ({bibliography_ratio:.2f})")

    lines = [
        f"# {title}",
        "",
        "## Abstract",
        "",
        abstract or "Abstract unavailable.",
        "",
    ]
    lines.extend(body_blocks)
    if appendix_snapshot:
        lines.extend(["", "## Appendix Snapshot", ""])
        for item in appendix_snapshot:
            lines.append(f"### {item['heading']}")
            lines.append("")
            lines.append(item["summary"] or "Appendix section detected, but no stable paragraph survived cleaning.")
            lines.append("")
    if figures:
        lines.extend(["", "## Figure Snapshot", ""])
        for item in figures:
            lines.append(f"### {item['label']} ({item['section']})")
            lines.append("")
            lines.append(item["caption"])
            if item.get("image_url"):
                lines.append("")
                lines.append(f"Image URL: {item['image_url']}")
            lines.append("")
    if tables:
        lines.extend(["", "## Table Snapshot", ""])
        for item in tables:
            lines.append(f"### {item['label']} ({item['section']})")
            lines.append("")
            lines.append(item["summary"])
            if item.get("markdown"):
                lines.append("")
                lines.append(item["markdown"])
            lines.append("")
    if equations:
        lines.extend(["", "## Equation Snapshot", ""])
        for item in equations:
            lines.append(f"### {item['label']} ({item['section']})")
            lines.append("")
            lines.append(item["text"])
            lines.append("")

    quality = {
        "body_chars": main_body_chars,
        "has_abstract": bool(abstract),
        "section_count": len(sections),
        "appendix_chars": appendix_chars,
        "appendix_sections": len(appendix_snapshot),
        "bibliography_ratio": round(bibliography_ratio, 4),
        "figure_count": len(figures),
        "table_count": len(tables),
        "equation_count": len(equations),
    }
    return CleanedArxivDocument(
        title=title,
        abstract=abstract,
        markdown="\n".join(lines).strip(),
        sections=sections,
        appendix_snapshot=appendix_snapshot,
        quality=quality,
        figures=figures,
        tables=tables,
        equations=equations,
        capture_fidelity="high",
    )


async def fetch_ar5iv_html(arxiv_id: str, timeout: float = 30.0) -> str:
    """Fetch canonical ar5iv HTML for an arXiv paper."""
    url = f"https://ar5iv.labs.arxiv.org/html/{arxiv_id}"
    async with httpx.AsyncClient(timeout=timeout, follow_redirects=True) as client:
        response = await client.get(url)
        response.raise_for_status()
        return response.text


async def capture_arxiv_source(
    paper: dict[str, Any],
    appendix_policy: str = "summary_only",
    min_body_chars: int = 1500,
    preserve_math: bool = True,
    preserve_figures: bool = True,
    preserve_tables: bool = True,
    max_figures: int = 12,
    max_tables: int = 12,
    max_equations: int = 24,
) -> CleanedArxivDocument:
    """Fetch and clean ar5iv HTML for a bound paper."""
    arxiv_id = paper_arxiv_id(paper)
    if not arxiv_id:
        raise ValueError("paper is not bound to arXiv")
    html = await fetch_ar5iv_html(arxiv_id)
    return await asyncio.to_thread(
        clean_ar5iv_html,
        html,
        appendix_policy,
        min_body_chars,
        preserve_math,
        preserve_figures,
        preserve_tables,
        max_figures,
        max_tables,
        max_equations,
    )


def _section_bucket(sections: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    buckets: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for section in sections:
        heading = str(section.get("heading", "")).lower()
        for bucket, keywords in _SECTION_KEYWORDS.items():
            if any(keyword in heading for keyword in keywords):
                buckets[bucket].append(section)
    return buckets


def _sentences(text: str) -> list[str]:
    parts = re.split(r"(?<=[.!?])\s+", _collapse_ws(text))
    return [part.strip() for part in parts if len(part.strip()) > 20]


def _take_sentences(texts: list[str], limit: int = 3) -> str:
    sentences: list[str] = []
    for text in texts:
        for sentence in _sentences(text):
            if sentence not in sentences:
                sentences.append(sentence)
            if len(sentences) >= limit:
                return " ".join(sentences)
    return " ".join(sentences)


def _take_paragraphs(texts: list[str], limit: int = 2) -> str:
    kept: list[str] = []
    for text in texts:
        if text and text not in kept:
            kept.append(text)
        if len(kept) >= limit:
            break
    return "\n\n".join(kept)


def _paragraphs_for_sections(sections: list[dict[str, Any]]) -> list[str]:
    paragraphs: list[str] = []
    for section in sections:
        paragraphs.extend(section.get("paragraphs", []))
    return paragraphs


def _captions_for_sections(sections: list[dict[str, Any]]) -> list[str]:
    captions: list[str] = []
    for section in sections:
        captions.extend(section.get("captions", []))
    return captions


def _structured_items_for_bucket(
    items: list[dict[str, Any]],
    bucket: str,
    *,
    field: str,
    limit: int = 2,
) -> list[str]:
    texts: list[str] = []
    keywords = _SECTION_KEYWORDS.get(bucket, ())
    for item in items:
        section = str(item.get("section", "")).lower()
        if keywords and not any(keyword in section for keyword in keywords):
            continue
        text = _collapse_ws(str(item.get(field, "")))
        if text and text not in texts:
            texts.append(text)
        if len(texts) >= limit:
            break
    return texts


def _fallback_from_abstract(abstract: str, default: str) -> str:
    summary = _take_sentences([abstract], limit=3)
    return summary or default


def build_crgp_dnl(
    paper: dict[str, Any],
    source_doc: CleanedArxivDocument,
) -> dict[str, Any]:
    """Build a deterministic CRGP-DNL note from cleaned source content."""
    sections = source_doc.sections
    buckets = _section_bucket(sections)
    intro_sections = [
        section for section in sections
        if "introduction" in str(section.get("heading", "")).lower()
    ]
    proposal_sections = buckets["proposal"]
    result_sections = buckets["results"]
    discussion_sections = buckets["discussion"]
    related_sections = buckets["related"]
    proposal_support = [
        *_captions_for_sections(proposal_sections),
        *_structured_items_for_bucket(source_doc.figures, "proposal", field="caption"),
        *_structured_items_for_bucket(source_doc.equations, "proposal", field="text"),
    ]
    result_support = [
        *_captions_for_sections(result_sections),
        *_structured_items_for_bucket(source_doc.figures, "results", field="caption"),
        *_structured_items_for_bucket(source_doc.tables, "results", field="summary"),
    ]
    discussion_support = [
        *_structured_items_for_bucket(source_doc.tables, "discussion", field="summary", limit=1),
        *(item.get("summary", "") for item in source_doc.appendix_snapshot[:1]),
    ]

    context_text = _take_sentences(
        [source_doc.abstract, *_paragraphs_for_sections(intro_sections or sections[:1])],
        limit=4,
    ) or _fallback_from_abstract(
        source_doc.abstract,
        "The cleaned source preserves too little introduction context to produce a richer note.",
    )

    related_text = _take_paragraphs(_paragraphs_for_sections(related_sections), limit=2) or (
        "The captured source does not expose a dedicated related-work section. Use the introduction and bibliography context in the source note for manual comparison."
    )

    gap_candidates = []
    for text in [source_doc.abstract, *(_paragraphs_for_sections(intro_sections or sections[:1]))]:
        for sentence in _sentences(text):
            lowered = sentence.lower()
            if any(token in lowered for token in ("however", "challenge", "limited", "bottleneck", "hard", "difficult")):
                gap_candidates.append(sentence)
    gap_text = " ".join(gap_candidates[:3]) or _fallback_from_abstract(
        source_doc.abstract,
        "The paper's problem framing is only weakly recoverable from the cleaned source.",
    )

    proposal_text = _take_paragraphs(
        [source_doc.abstract, *_paragraphs_for_sections(proposal_sections), *proposal_support],
        limit=3,
    ) or _fallback_from_abstract(
        source_doc.abstract,
        "The proposal could not be tied to a dedicated method section in the cleaned source.",
    )

    result_text = _take_paragraphs([*_paragraphs_for_sections(result_sections), *result_support], limit=3)
    if not result_text:
        result_text = _take_sentences([source_doc.abstract], limit=3) or (
            "The cleaned source did not surface a stable evaluation section, so key results remain uncertain."
        )

    discussion_text = _take_paragraphs(
        [*_paragraphs_for_sections(discussion_sections), *discussion_support],
        limit=3,
    ) or (
        "The source does not contain a dedicated discussion or limitations section, so downstream compilation should stay conservative."
    )

    next_steps = []
    for sentence in _sentences(discussion_text):
        lowered = sentence.lower()
        if any(token in lowered for token in ("future", "limitation", "next", "open", "improve")):
            next_steps.append(sentence)
    next_steps_text = " ".join(next_steps[:3]) or (
        "Follow up by checking whether the captured appendix, ablations, or supplementary material clarifies open limitations and transfer behavior."
    )

    evidence = {
        "Context": ["Abstract"] + [section["heading"] for section in intro_sections[:2]],
        "Related Work": [section["heading"] for section in related_sections[:2]],
        "Gap": [section["heading"] for section in intro_sections[:1]] or ["Abstract"],
        "Proposal": (
            [section["heading"] for section in proposal_sections[:2]]
            + (["Equation Snapshot"] if proposal_support else [])
        ) or ["Abstract"],
        "Key Results": (
            [section["heading"] for section in result_sections[:2]]
            + (["Figure Snapshot"] if source_doc.figures else [])
            + (["Table Snapshot"] if source_doc.tables else [])
        ) or ["Abstract"],
        "Discussion": [section["heading"] for section in discussion_sections[:2]] + (
            ["Appendix Snapshot"] if source_doc.appendix_snapshot else []
        ),
        "Next Steps": [section["heading"] for section in discussion_sections[:1]] or ["Appendix Snapshot"],
    }

    confidence_hits = sum(
        1
        for bucket in ("proposal", "results", "discussion")
        if buckets[bucket]
    )
    confidence = round(min(0.45 + 0.12 * confidence_hits + (0.08 if source_doc.abstract else 0.0), 0.95), 2)

    sections_payload = {
        "Context": context_text,
        "Related Work": related_text,
        "Gap": gap_text,
        "Proposal": proposal_text,
        "Key Results": result_text,
        "Discussion": discussion_text,
        "Next Steps": next_steps_text,
    }
    return {
        "paper_id": paper_id(paper),
        "sections": sections_payload,
        "evidence": evidence,
        "confidence": confidence,
    }
