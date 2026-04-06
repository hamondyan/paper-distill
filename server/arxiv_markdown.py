"""Convert arXiv HTML fragments to Markdown with configurable citation handling."""
from __future__ import annotations

import re

from bs4 import BeautifulSoup
from bs4.element import NavigableString, Tag


_EQUATION_TABLE_RE = re.compile(r"ltx_equationgroup|ltx_eqn_align|ltx_eqn_table")


def convert_fragment_to_markdown(
    html: str,
    *,
    remove_inline_citations: bool = False,
    remove_internal_links: bool = True,
) -> str:
    soup = BeautifulSoup(html, "html.parser")
    _strip_unwanted_elements(soup)
    convert_all_mathml_to_latex(soup)
    fix_tabular_tables(soup)
    blocks = _serialize_children(
        soup,
        remove_inline_citations=remove_inline_citations,
        remove_internal_links=remove_internal_links,
    )
    return "\n\n".join(block for block in blocks if block).strip()


def node_text_content(
    node: Tag,
    *,
    remove_inline_citations: bool = False,
    remove_internal_links: bool = True,
) -> str:
    clone = BeautifulSoup(str(node), "html.parser")
    root = clone.find()
    if not isinstance(root, Tag):
        return ""
    _strip_unwanted_elements(clone)
    convert_all_mathml_to_latex(clone)
    fix_tabular_tables(clone)
    if root.name in {"p", "figcaption", "cite"}:
        return _cleanup_inline_text(
            _serialize_inline(
                root,
                remove_inline_citations=remove_inline_citations,
                remove_internal_links=remove_internal_links,
            )
        )
    return _cleanup_inline_text(
        " ".join(
            _serialize_children(
                root,
                remove_inline_citations=remove_inline_citations,
                remove_internal_links=remove_internal_links,
            )
        )
    )


def table_html_to_markdown(
    html: str,
    *,
    remove_inline_citations: bool = False,
    remove_internal_links: bool = True,
) -> str:
    soup = BeautifulSoup(html, "html.parser")
    _strip_unwanted_elements(soup)
    convert_all_mathml_to_latex(soup)
    fix_tabular_tables(soup)
    table = soup.find("table")
    if not isinstance(table, Tag):
        return ""
    return _serialize_table(
        table,
        remove_inline_citations=remove_inline_citations,
        remove_internal_links=remove_internal_links,
    )


def _strip_unwanted_elements(soup: BeautifulSoup) -> None:
    for tag in soup.find_all(["script", "style", "noscript", "link", "meta"]):
        tag.decompose()
    for tag in soup.select("nav.ltx_page_navbar, nav.ltx_TOC"):
        tag.decompose()
    for tag in soup.select("button.sr-only, div.package-alerts, div.ltx_pagination, footer"):
        tag.decompose()


def convert_all_mathml_to_latex(root: BeautifulSoup) -> None:
    for math in root.find_all("math"):
        annotation = math.find("annotation", attrs={"encoding": "application/x-tex"})
        if annotation and annotation.text:
            latex_source = annotation.text.strip()
            latex_source = re.sub(r"(?<!\\)%", "", latex_source)
            latex_source = re.sub(r"\\([_^])", r"\1", latex_source)
            latex_source = re.sub(r"\\(?=[\[\]])", "", latex_source)
            math.replace_with(f"${latex_source}$")
        else:
            math.replace_with(math.get_text(" ", strip=True))


def fix_tabular_tables(root: BeautifulSoup) -> None:
    tables = root.find_all("table", class_=re.compile(r"ltx_tabular"))
    for table in tables:
        _remove_all_attributes(table)
        for child in table.find_all(["tbody", "thead", "tfoot", "tr", "td", "th"]):
            _remove_all_attributes(child)


def _remove_all_attributes(tag: Tag) -> None:
    tag.attrs = {}


def _serialize_children(
    container: Tag,
    *,
    remove_inline_citations: bool = False,
    remove_internal_links: bool = True,
) -> list[str]:
    blocks: list[str] = []
    for child in container.children:
        if isinstance(child, NavigableString):
            continue
        if not isinstance(child, Tag):
            continue
        blocks.extend(
            _serialize_block(
                child,
                remove_inline_citations=remove_inline_citations,
                remove_internal_links=remove_internal_links,
            )
        )
    return blocks


def _serialize_block(
    tag: Tag,
    *,
    remove_inline_citations: bool = False,
    remove_internal_links: bool = True,
) -> list[str]:
    if tag.name in {"section", "article", "div", "span"}:
        return _serialize_children(
            tag,
            remove_inline_citations=remove_inline_citations,
            remove_internal_links=remove_internal_links,
        )
    if tag.name in {"h1", "h2", "h3", "h4", "h5", "h6"}:
        heading = _normalize_text(tag.get_text(" ", strip=True))
        if not heading:
            return []
        return [f"{'#' * int(tag.name[1])} {heading}"]
    if tag.name == "p":
        paragraph = _cleanup_inline_text(
            _serialize_inline(
                tag,
                remove_inline_citations=remove_inline_citations,
                remove_internal_links=remove_internal_links,
            )
        )
        return [paragraph] if paragraph else []
    if tag.name in {"ul", "ol"}:
        lines = _serialize_list(
            tag,
            remove_inline_citations=remove_inline_citations,
            remove_internal_links=remove_internal_links,
        )
        return ["\n".join(lines)] if lines else []
    if tag.name == "figure":
        figure = _serialize_figure(
            tag,
            remove_inline_citations=remove_inline_citations,
            remove_internal_links=remove_internal_links,
        )
        return [figure] if figure else []
    if tag.name == "table":
        table_md = _serialize_table(
            tag,
            remove_inline_citations=remove_inline_citations,
            remove_internal_links=remove_internal_links,
        )
        return [table_md] if table_md else []
    if tag.name == "blockquote":
        content = _normalize_text(
            _serialize_inline(
                tag,
                remove_inline_citations=remove_inline_citations,
                remove_internal_links=remove_internal_links,
            )
        )
        return ["> " + content] if content else []
    if tag.name == "br":
        return []
    return _serialize_children(
        tag,
        remove_inline_citations=remove_inline_citations,
        remove_internal_links=remove_internal_links,
    )


def _is_citation_link(href: str | None) -> bool:
    if not href:
        return False
    return "#bib." in href or href.startswith("#bib")


def _is_internal_paper_link(href: str | None) -> bool:
    if not href:
        return False
    return "arxiv.org/html/" in href and "#" in href and "#bib" not in href


def _serialize_inline(
    node: Tag | NavigableString,
    *,
    remove_inline_citations: bool = False,
    remove_internal_links: bool = True,
) -> str:
    if isinstance(node, NavigableString):
        return str(node)
    if node.name == "br":
        return "\n"
    if node.name in {"em", "i"}:
        return f"*{_serialize_children_inline(node, remove_inline_citations=remove_inline_citations, remove_internal_links=remove_internal_links)}*"
    if node.name in {"strong", "b"}:
        return f"**{_serialize_children_inline(node, remove_inline_citations=remove_inline_citations, remove_internal_links=remove_internal_links)}**"
    if node.name == "a":
        text = _serialize_children_inline(
            node,
            remove_inline_citations=remove_inline_citations,
            remove_internal_links=remove_internal_links,
        ).strip()
        href = node.get("href")
        if _is_citation_link(href):
            return "" if remove_inline_citations else text
        if remove_internal_links and _is_internal_paper_link(href):
            return text
        if href:
            return f"[{text or href}]({href})"
        return text
    if node.name == "sup":
        text = _serialize_children_inline(
            node,
            remove_inline_citations=remove_inline_citations,
            remove_internal_links=remove_internal_links,
        ).strip()
        return f"^{text}" if text else ""
    if node.name == "cite":
        if remove_inline_citations and "ltx_cite" in node.get("class", []):
            return ""
        return _serialize_children_inline(
            node,
            remove_inline_citations=remove_inline_citations,
            remove_internal_links=remove_internal_links,
        )
    if node.name == "math":
        text = node.get_text(" ", strip=True)
        return f"${text}$" if text else ""
    if "ltx_note" in node.get("class", []):
        text = _normalize_text(
            _serialize_children_inline(
                node,
                remove_inline_citations=remove_inline_citations,
                remove_internal_links=remove_internal_links,
            )
        )
        return f"({text})" if text else ""
    return _serialize_children_inline(
        node,
        remove_inline_citations=remove_inline_citations,
        remove_internal_links=remove_internal_links,
    )


def _serialize_children_inline(
    tag: Tag,
    *,
    remove_inline_citations: bool = False,
    remove_internal_links: bool = True,
) -> str:
    return "".join(
        _serialize_inline(
            child,
            remove_inline_citations=remove_inline_citations,
            remove_internal_links=remove_internal_links,
        )
        for child in tag.children
    )


def _serialize_list(
    list_tag: Tag,
    indent: int = 0,
    *,
    remove_inline_citations: bool = False,
    remove_internal_links: bool = True,
) -> list[str]:
    lines: list[str] = []
    for item in list_tag.find_all("li", recursive=False):
        item_text_parts: list[str] = []
        nested_lists: list[Tag] = []
        for child in item.children:
            if isinstance(child, Tag) and child.name in {"ul", "ol"}:
                nested_lists.append(child)
            else:
                item_text_parts.append(
                    _serialize_inline(
                        child,
                        remove_inline_citations=remove_inline_citations,
                        remove_internal_links=remove_internal_links,
                    )
                )
        item_text = _cleanup_inline_text("".join(item_text_parts))
        prefix = "  " * indent + "- "
        lines.append(prefix + item_text if item_text else prefix.rstrip())
        for nested in nested_lists:
            lines.extend(
                _serialize_list(
                    nested,
                    indent + 1,
                    remove_inline_citations=remove_inline_citations,
                    remove_internal_links=remove_internal_links,
                )
            )
    return lines


def _serialize_table(
    table: Tag,
    *,
    remove_inline_citations: bool = False,
    remove_internal_links: bool = True,
) -> str:
    classes = " ".join(table.get("class", []))
    if _EQUATION_TABLE_RE.search(classes):
        eqn_text = _normalize_text(table.get_text(" ", strip=True))
        return f"$$ {eqn_text} $$" if eqn_text else ""

    rows: list[list[str]] = []
    tbody_elements = table.find_all(["tbody", "thead", "tfoot"], recursive=False)
    if tbody_elements:
        for tbody in tbody_elements:
            for row in tbody.find_all("tr", recursive=False):
                cells = row.find_all(["th", "td"], recursive=False)
                if not cells:
                    continue
                values = []
                for cell in cells:
                    cell_text = _cleanup_inline_text(
                        _serialize_inline(
                            cell,
                            remove_inline_citations=remove_inline_citations,
                            remove_internal_links=remove_internal_links,
                        )
                    ).replace("\n", "<br>")
                    values.append(cell_text)
                rows.append(values)
    else:
        for row in table.find_all("tr", recursive=False):
            cells = row.find_all(["th", "td"], recursive=False)
            if not cells:
                continue
            values = []
            for cell in cells:
                cell_text = _cleanup_inline_text(
                    _serialize_inline(
                        cell,
                        remove_inline_citations=remove_inline_citations,
                        remove_internal_links=remove_internal_links,
                    )
                ).replace("\n", "<br>")
                values.append(cell_text)
            rows.append(values)
    if not rows:
        return ""
    max_cols = max(len(row) for row in rows)
    normalized = [row + [""] * (max_cols - len(row)) for row in rows]
    header = normalized[0]
    lines = [
        "| " + " | ".join(header) + " |",
        "| " + " | ".join("---" for _ in header) + " |",
    ]
    for row in normalized[1:]:
        lines.append("| " + " | ".join(row) + " |")
    return "\n".join(lines)


def _serialize_figure(
    figure: Tag,
    *,
    remove_inline_citations: bool = False,
    remove_internal_links: bool = True,
) -> str:
    figure_classes = " ".join(figure.get("class", []))
    is_table_figure = "ltx_table" in figure_classes
    caption_tag = figure.find("figcaption")
    caption = ""
    if isinstance(caption_tag, Tag):
        caption = _normalize_text(
            _serialize_inline(
                caption_tag,
                remove_inline_citations=remove_inline_citations,
                remove_internal_links=remove_internal_links,
            )
        )
    lines: list[str] = []
    if is_table_figure:
        table = figure.find("table")
        if isinstance(table, Tag):
            table_md = _serialize_table(
                table,
                remove_inline_citations=remove_inline_citations,
                remove_internal_links=remove_internal_links,
            )
            if caption:
                lines.append(f"**{caption}**")
            if table_md:
                lines.append(table_md)
        elif caption:
            lines.append(f"Table: {caption}")
    else:
        img = figure.find("img")
        src = img.get("src") if isinstance(img, Tag) else None
        alt = img.get("alt") if isinstance(img, Tag) else None
        if caption:
            lines.append(f"Figure: {caption}")
        if src:
            lines.append(f"{alt or 'Image'}: {src}")
    return "\n".join(lines).strip()


def _normalize_text(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def _cleanup_inline_text(text: str) -> str:
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\s*\n\s*", "\n", text)
    return text.strip()
