# ArXiv Capture Modernization Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Modernize Paper Distill's arXiv capture pipeline by selectively importing `arxiv2md`'s strongest fetch, formula, table, filter, and citation behaviors while preserving the existing `CleanedArxivDocument` contract.

**Architecture:** Keep `server/arxiv_capture.py` as the public facade and move lower-level HTML fetch, parsing, section filtering, and Markdown serialization into focused helper modules. Adapt those helpers back into the current `CleanedArxivDocument` data model so raw source notes, sidecars, and CRGP-DNL generation remain compatible. Land the refactor in small behavior-preserving phases and verify each with targeted tests before moving on.

**Tech Stack:** Python 3.10, `httpx`, `beautifulsoup4`, `rapidfuzz`, `uv`, `pytest`, `unittest`

---

### Task 1: Establish regression coverage for the new boundaries

**Files:**
- Create: `tests/test_arxiv_html_fetch.py`
- Create: `tests/test_arxiv_section_filters.py`
- Create: `tests/test_arxiv_markdown.py`
- Modify: `tests/test_arxiv_capture.py`

- [ ] **Step 1: Write failing fetch fallback tests**

```python
from __future__ import annotations

import asyncio
import unittest
from unittest.mock import AsyncMock, patch

from server.arxiv_html_fetch import fetch_arxiv_html_with_fallback


class ArxivHtmlFetchTest(unittest.TestCase):
    def test_fetch_prefers_native_html(self) -> None:
        async def run() -> tuple[str, str]:
            with patch("server.arxiv_html_fetch._fetch_html", new=AsyncMock(return_value="<article></article>")):
                return await fetch_arxiv_html_with_fallback("2501.00001")

        html, source = asyncio.run(run())
        self.assertEqual(html, "<article></article>")
        self.assertEqual(source, "arxiv_native_html")

    def test_fetch_falls_back_to_ar5iv_when_native_unavailable(self) -> None:
        async def fake_fetch(url: str, timeout: float = 30.0) -> str:
            if "arxiv.org/html" in url:
                raise RuntimeError("This paper does not have an HTML version available on arXiv.")
            return "<article>fallback</article>"

        async def run() -> tuple[str, str]:
            with patch("server.arxiv_html_fetch._fetch_html", new=fake_fetch):
                return await fetch_arxiv_html_with_fallback("2501.00001")

        html, source = asyncio.run(run())
        self.assertEqual(html, "<article>fallback</article>")
        self.assertEqual(source, "ar5iv_html")
```

- [ ] **Step 2: Run fetch tests to verify they fail**

Run: `uv run --with pytest pytest -q tests/test_arxiv_html_fetch.py`
Expected: FAIL with `ModuleNotFoundError` or import errors because `server.arxiv_html_fetch` does not exist yet.

- [ ] **Step 3: Write failing section normalization tests**

```python
from __future__ import annotations

import unittest

from server.arxiv_section_filters import normalize_section_title, should_keep_section


class ArxivSectionFiltersTest(unittest.TestCase):
    def test_normalize_section_title_strips_numbering(self) -> None:
        self.assertEqual(normalize_section_title("1 Introduction"), "introduction")
        self.assertEqual(normalize_section_title("A.1 Appendix"), "appendix")

    def test_should_keep_section_supports_exclude(self) -> None:
        self.assertFalse(should_keep_section("References", mode="exclude", selected=["references"]))
        self.assertTrue(should_keep_section("Method", mode="exclude", selected=["references"]))
```

- [ ] **Step 4: Run section filter tests to verify they fail**

Run: `uv run --with pytest pytest -q tests/test_arxiv_section_filters.py`
Expected: FAIL because `server.arxiv_section_filters` does not exist yet.

- [ ] **Step 5: Write failing serializer tests**

```python
from __future__ import annotations

import unittest

from server.arxiv_markdown import convert_fragment_to_markdown


class ArxivMarkdownTest(unittest.TestCase):
    def test_convert_fragment_renders_math_and_table(self) -> None:
        html = """
        <div><p>Equation <math><annotation encoding="application/x-tex">x+y</annotation></math></p></div>
        <figure class="ltx_table">
          <table class="ltx_tabular">
            <thead><tr><th>A</th><th>B</th></tr></thead>
            <tbody><tr><td>1</td><td>2</td></tr></tbody>
          </table>
          <figcaption>Table 1: Example.</figcaption>
        </figure>
        """
        markdown = convert_fragment_to_markdown(html)
        self.assertIn("$x+y$", markdown)
        self.assertIn("Table 1: Example.", markdown)
        self.assertIn("| A | B |", markdown)
```

- [ ] **Step 6: Run serializer tests to verify they fail**

Run: `uv run --with pytest pytest -q tests/test_arxiv_markdown.py`
Expected: FAIL because `server.arxiv_markdown` does not exist yet.

- [ ] **Step 7: Add failing integration assertions for appendix and reference policies**

```python
def test_clean_ar5iv_html_supports_drop_appendix_and_remove_inline_citations(self) -> None:
    cleaned = clean_ar5iv_html(
        _SAMPLE_AR5IV_HTML,
        appendix_policy="drop",
        min_body_chars=300,
        remove_inline_citations=True,
    )
    assert "Appendix Snapshot" not in cleaned.markdown
```

- [ ] **Step 8: Run the focused capture tests to verify they fail**

Run: `uv run --with pytest pytest -q tests/test_arxiv_capture.py`
Expected: FAIL on the newly added policy tests because the options are not implemented yet.

### Task 2: Extract the HTML fetch and section filtering modules

**Files:**
- Create: `server/arxiv_html_fetch.py`
- Create: `server/arxiv_section_filters.py`
- Modify: `server/arxiv_capture.py`
- Test: `tests/test_arxiv_html_fetch.py`
- Test: `tests/test_arxiv_section_filters.py`

- [ ] **Step 1: Implement the minimal fetch helper and provenance return**

```python
async def _fetch_html(url: str, timeout: float = 30.0) -> str:
    async with httpx.AsyncClient(timeout=timeout, follow_redirects=True) as client:
        response = await client.get(url)
        response.raise_for_status()
        return response.text


async def fetch_arxiv_html_with_fallback(arxiv_id: str, timeout: float = 30.0) -> tuple[str, str]:
    native_url = f"https://arxiv.org/html/{arxiv_id}"
    ar5iv_url = f"https://ar5iv.labs.arxiv.org/html/{arxiv_id}"
    try:
        return await _fetch_html(native_url, timeout=timeout), "arxiv_native_html"
    except Exception as exc:
        if "does not have an HTML version" not in str(exc) and "404" not in str(exc):
            raise
    return await _fetch_html(ar5iv_url, timeout=timeout), "ar5iv_html"
```

- [ ] **Step 2: Implement section title normalization and include/exclude helpers**

```python
def normalize_section_title(title: str) -> str:
    title = re.sub(r"^[\\dA-Za-z.\\-]+\\s+", "", title.strip().lower())
    return re.sub(r"\\s+", " ", title)


def should_keep_section(title: str, *, mode: str = "exclude", selected: Iterable[str] | None = None) -> bool:
    selected_titles = {normalize_section_title(item) for item in (selected or []) if item.strip()}
    if not selected_titles:
        return True
    normalized = normalize_section_title(title)
    if mode == "include":
        return normalized in selected_titles
    return normalized not in selected_titles
```

- [ ] **Step 3: Wire `capture_arxiv_source` through the new fetch helper**

```python
html, fetch_source = await fetch_arxiv_html_with_fallback(arxiv_id)
doc = await asyncio.to_thread(clean_ar5iv_html, html, ...)
if fetch_source == "arxiv_native_html":
    doc.capture_fidelity = "high"
return doc
```

- [ ] **Step 4: Run the new unit tests to verify they pass**

Run: `uv run --with pytest pytest -q tests/test_arxiv_html_fetch.py tests/test_arxiv_section_filters.py`
Expected: PASS

- [ ] **Step 5: Run the existing capture tests to verify no regression**

Run: `uv run --with pytest pytest -q tests/test_arxiv_capture.py`
Expected: PASS except for the new policy tests still waiting on later tasks.

### Task 3: Introduce the Markdown serializer module using adapted `arxiv2md` logic

**Files:**
- Create: `server/arxiv_markdown.py`
- Modify: `server/arxiv_capture.py`
- Test: `tests/test_arxiv_markdown.py`
- Test: `tests/test_arxiv_capture.py`

- [ ] **Step 1: Implement MathML-to-LaTeX conversion and table serialization**

```python
def convert_all_mathml_to_latex(root: BeautifulSoup) -> None:
    for math in root.find_all("math"):
        annotation = math.find("annotation", attrs={"encoding": "application/x-tex"})
        if annotation and annotation.text:
            latex_source = annotation.text.strip()
            latex_source = re.sub(r"(?<!\\\\)%", "", latex_source)
            latex_source = re.sub(r"\\\\([_^])", r"\\1", latex_source)
            latex_source = re.sub(r"\\\\(?=[\\[\\]])", "", latex_source)
            math.replace_with(f"${latex_source}$")
        else:
            math.replace_with(math.get_text(" ", strip=True))
```

- [ ] **Step 2: Port the table and figure serializer behavior**

```python
def _serialize_table(table: Tag, *, remove_inline_citations: bool = False) -> str:
    rows = []
    tbody_elements = table.find_all(["tbody", "thead", "tfoot"], recursive=False)
    ...
    return "\\n".join(lines)


def _serialize_figure(figure: Tag, *, remove_inline_citations: bool = False) -> str:
    ...
```

- [ ] **Step 3: Expose a public fragment conversion entrypoint**

```python
def convert_fragment_to_markdown(html: str, *, remove_inline_citations: bool = False, remove_internal_links: bool = True) -> str:
    soup = BeautifulSoup(html, "html.parser")
    _strip_unwanted_elements(soup)
    convert_all_mathml_to_latex(soup)
    fix_tabular_tables(soup)
    return "\\n\\n".join(_serialize_children(soup, remove_inline_citations=remove_inline_citations, remove_internal_links=remove_internal_links)).strip()
```

- [ ] **Step 4: Update `clean_ar5iv_html` to use the shared serializer for paragraph/caption/table Markdown where helpful**

```python
table_markdown = convert_fragment_to_markdown(str(table_tag), remove_inline_citations=remove_inline_citations)
```

- [ ] **Step 5: Run serializer and capture tests**

Run: `uv run --with pytest pytest -q tests/test_arxiv_markdown.py tests/test_arxiv_capture.py`
Expected: PASS for math/table coverage and no regression in structured counts.

### Task 4: Add appendix, reference, and citation policy controls

**Files:**
- Modify: `server/arxiv_capture.py`
- Modify: `server/server.py`
- Modify: `server/config.py`
- Modify: `settings.example.json`
- Test: `tests/test_arxiv_capture.py`
- Test: `tests/test_server_tools.py`

- [ ] **Step 1: Expand `clean_ar5iv_html` and `capture_arxiv_source` signatures**

```python
def clean_ar5iv_html(
    html: str,
    appendix_policy: str = "summary",
    min_body_chars: int = 1500,
    preserve_math: bool = True,
    preserve_figures: bool = True,
    preserve_tables: bool = True,
    max_figures: int = 12,
    max_tables: int = 12,
    max_equations: int = 24,
    remove_refs: bool = True,
    remove_inline_citations: bool = False,
    remove_internal_links: bool = True,
) -> CleanedArxivDocument:
    ...
```

- [ ] **Step 2: Implement appendix modes**

```python
if appendix_policy == "drop":
    continue
if appendix_policy == "summary":
    ...
```

- [ ] **Step 3: Thread the policy options from server settings into capture calls**

```python
source_doc = await capture_arxiv_source(
    paper,
    appendix_policy=appendix_policy,
    min_body_chars=min_body_chars,
    preserve_math=...,
    remove_refs=bool(options.get("remove_refs", True)),
    remove_inline_citations=bool(options.get("remove_inline_citations", False)),
    remove_internal_links=bool(options.get("remove_internal_links", True)),
)
```

- [ ] **Step 4: Update sample settings defaults**

```json
"capture": {
  "appendix_policy": "summary",
  "remove_refs": true,
  "remove_inline_citations": false,
  "remove_internal_links": true
}
```

- [ ] **Step 5: Run focused tests for policy behavior**

Run: `uv run --with pytest pytest -q tests/test_arxiv_capture.py tests/test_server_tools.py`
Expected: PASS

### Task 5: Thin `server/arxiv_capture.py` and preserve the adapter contract

**Files:**
- Modify: `server/arxiv_capture.py`
- Create: `server/arxiv_html_parser.py`
- Create: `server/arxiv_capture_adapter.py`
- Test: `tests/test_arxiv_capture.py`
- Test: `tests/test_paper_add.py`

- [ ] **Step 1: Move author/section parsing helpers into `server/arxiv_html_parser.py`**

```python
@dataclass
class ParsedArxivHtml:
    title: str
    abstract: str
    authors: list[str]
    sections: list[dict[str, Any]]
```

- [ ] **Step 2: Create an adapter that builds `CleanedArxivDocument`**

```python
def build_cleaned_document(... ) -> CleanedArxivDocument:
    return CleanedArxivDocument(
        title=title,
        abstract=abstract,
        markdown=markdown,
        sections=sections,
        appendix_snapshot=appendix_snapshot,
        quality=quality,
        figures=figures,
        tables=tables,
        equations=equations,
        capture_fidelity=capture_fidelity,
    )
```

- [ ] **Step 3: Simplify `server/arxiv_capture.py` to orchestration only**

```python
html, fetch_source = await fetch_arxiv_html_with_fallback(arxiv_id)
parsed = parse_arxiv_html(html)
return build_cleaned_document(...)
```

- [ ] **Step 4: Run the main ingestion regression tests**

Run: `uv run --with pytest pytest -q tests/test_arxiv_capture.py tests/test_paper_add.py`
Expected: PASS, excluding unrelated baseline failures outside the capture modernization scope.

### Task 6: Verify the end state and document residual baseline failures

**Files:**
- Modify: `docs/superpowers/plans/2026-04-06-arxiv-capture-modernization.md`

- [ ] **Step 1: Run the full relevant verification suite**

Run: `uv run --with pytest pytest -q tests/test_arxiv_html_fetch.py tests/test_arxiv_section_filters.py tests/test_arxiv_markdown.py tests/test_arxiv_capture.py tests/test_paper_add.py tests/test_server_tools.py`
Expected: PASS for the capture modernization scope.

- [ ] **Step 2: Run the full project suite for awareness of repository-wide status**

Run: `uv run --with pytest pytest -q`
Expected: Same pre-existing failures observed at baseline unless separately fixed:
- `tests/test_paper_add.py::PaperAddTest::test_add_paper_passes_topic_keys_and_collection_override`
- `tests/test_scoring.py::ScoringTest::test_discover_merges_matched_topics_for_same_paper`

- [ ] **Step 3: Update plan notes with actual verification results**

```markdown
Verification notes:
- Scope tests: PASS
- Full suite: baseline repository still contains 2 unrelated failures
```

- [ ] **Step 4: Commit the implementation**

```bash
git add server/arxiv_capture.py server/arxiv_html_fetch.py server/arxiv_section_filters.py server/arxiv_markdown.py server/arxiv_html_parser.py server/arxiv_capture_adapter.py server/server.py server/config.py settings.example.json tests/test_arxiv_html_fetch.py tests/test_arxiv_section_filters.py tests/test_arxiv_markdown.py tests/test_arxiv_capture.py tests/test_paper_add.py tests/test_server_tools.py docs/superpowers/plans/2026-04-06-arxiv-capture-modernization.md
git commit -m "feat: modernize arxiv capture pipeline"
```

## Verification Notes

- Scope suite: `uv run --with pytest pytest -q tests/test_arxiv_html_fetch.py tests/test_arxiv_section_filters.py tests/test_arxiv_markdown.py tests/test_arxiv_capture.py tests/test_paper_add.py -k "not passes_topic_keys_and_collection_override"` -> `22 passed, 1 deselected`
- Full suite: `uv run --with pytest pytest -q` -> `47 passed, 2 failed`
- Repository-wide residual failures remain unchanged from baseline:
  - `tests/test_paper_add.py::PaperAddTest::test_add_paper_passes_topic_keys_and_collection_override`
  - `tests/test_scoring.py::ScoringTest::test_discover_merges_matched_topics_for_same_paper`
