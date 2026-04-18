# Agent-Resolved Paper Intake Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Let the agent resolve natural paper references to arXiv identities, then ingest one or many resolved arXiv URLs, IDs, or arXiv DOI values through the existing `ingest_and_read` interface.

**Architecture:** Keep semantic paper resolution outside the MCP server and document it in the `paper-intake` skill. Extend deterministic server intake so `ingest_and_read_v3` can parse multiple arXiv-bound identifiers, capture each valid item independently, and return batch-friendly per-item results while preserving existing single-item compatibility.

**Tech Stack:** Python 3.11, `unittest`, `pytest`, `AsyncMock`, existing Paper Distill MCP helpers, arXiv native HTML capture with ar5iv fallback.

---

## File Structure

- Modify `server/paper_utils.py`
  - Extend `extract_arxiv_id()` so it accepts bare arXiv IDs such as `1706.03762` and versioned bare IDs such as `1706.03762v7`.
  - Preserve existing support for arXiv URLs, `arxiv:` identifiers, and arXiv DOI values.

- Modify `server/v3_ingest.py`
  - Add direct-input splitting helpers for newline, Markdown bullet, numbered list, comma, and semicolon formats.
  - Add per-item direct ingest handling for arXiv-bound identifiers.
  - Preserve `approved` mode exactly.
  - Preserve existing top-level error compatibility for single invalid direct inputs and single capture failures.

- Modify `tests/test_paper_utils.py`
  - Add tests for bare and versioned arXiv IDs.

- Modify `tests/test_v3_ingest.py`
  - Add tests for batch newline input, bullet input, mixed valid/invalid input, duplicate IDs, bare ID direct ingest, and single invalid compatibility.
  - Update the direct rejection test only if needed so it also checks the new `errors` shape.

- Modify `skills/paper-intake/SKILL.md`
  - Update routing rules so natural titles, acronyms, aliases, and project names are resolved by the agent before MCP capture.
  - Keep `approved` behavior unchanged.

- Modify `commands/ingest.md`, `docs/commands.md`, and `README.md`
  - Document that users can provide natural paper references to the agent, while `ingest_and_read` receives resolved arXiv identities.
  - Document batch input support.

---

### Task 1: Extend arXiv ID Extraction

**Files:**
- Modify: `tests/test_paper_utils.py`
- Modify: `server/paper_utils.py`

- [ ] **Step 1: Add failing tests for bare arXiv IDs**

Append this test method to the existing test class in `tests/test_paper_utils.py`. If the file uses standalone functions instead of a class, add the two assertions as a new standalone test function.

```python
def test_extract_arxiv_id_accepts_bare_ids() -> None:
    from server.paper_utils import extract_arxiv_id

    assert extract_arxiv_id("1706.03762") == "1706.03762"
    assert extract_arxiv_id("1706.03762v7") == "1706.03762"
    assert extract_arxiv_id("  2501.00001  ") == "2501.00001"
```

- [ ] **Step 2: Run the new test and verify it fails**

Run:

```bash
uv run pytest tests/test_paper_utils.py::test_extract_arxiv_id_accepts_bare_ids -v
```

Expected: FAIL because `extract_arxiv_id("1706.03762")` currently returns `""`.

- [ ] **Step 3: Implement bare ID extraction**

Replace `extract_arxiv_id()` in `server/paper_utils.py` with:

```python
def extract_arxiv_id(value: str) -> str:
    if not value:
        return ""
    cleaned = value.strip()
    match = re.search(
        r"(?:arxiv\.org/(?:abs|pdf)/|arxiv:|arxiv\.)(\d{4}\.\d{4,5})(?:v\d+)?",
        cleaned,
        re.IGNORECASE,
    )
    if match:
        return match.group(1)
    bare = re.fullmatch(r"(\d{4}\.\d{4,5})(?:v\d+)?", cleaned, re.IGNORECASE)
    return bare.group(1) if bare else ""
```

- [ ] **Step 4: Run the focused paper utils tests**

Run:

```bash
uv run pytest tests/test_paper_utils.py -v
```

Expected: PASS.

- [ ] **Step 5: Commit Task 1**

Run:

```bash
git add server/paper_utils.py tests/test_paper_utils.py
git commit -m "feat: accept bare arxiv ids"
```

---

### Task 2: Add Direct Batch Parsing Helpers

**Files:**
- Modify: `tests/test_v3_ingest.py`
- Modify: `server/v3_ingest.py`

- [ ] **Step 1: Add failing tests for direct input splitting**

Add these test methods inside `class V3IngestTest(unittest.TestCase)` in `tests/test_v3_ingest.py`:

```python
def test_split_direct_input_items_handles_agent_batch_formats(self) -> None:
    from server.v3_ingest import _split_direct_input_items

    raw = """
    - https://arxiv.org/abs/2405.12213
    2. 1706.03762
    3) 10.48550/arxiv.2410.24164; https://arxiv.org/pdf/2501.00001.pdf
    """

    self.assertEqual(
        _split_direct_input_items(raw),
        [
            "https://arxiv.org/abs/2405.12213",
            "1706.03762",
            "10.48550/arxiv.2410.24164",
            "https://arxiv.org/pdf/2501.00001.pdf",
        ],
    )

def test_split_direct_input_items_keeps_single_url_intact(self) -> None:
    from server.v3_ingest import _split_direct_input_items

    self.assertEqual(
        _split_direct_input_items("https://arxiv.org/abs/2405.12213"),
        ["https://arxiv.org/abs/2405.12213"],
    )
```

- [ ] **Step 2: Run the new parsing tests and verify they fail**

Run:

```bash
uv run pytest tests/test_v3_ingest.py::V3IngestTest::test_split_direct_input_items_handles_agent_batch_formats tests/test_v3_ingest.py::V3IngestTest::test_split_direct_input_items_keeps_single_url_intact -v
```

Expected: FAIL with an import error because `_split_direct_input_items` does not exist yet.

- [ ] **Step 3: Add parsing helpers to `server/v3_ingest.py`**

Add `import re` near the top of `server/v3_ingest.py`:

```python
import hashlib
import re
from datetime import datetime, timezone
```

Then add these helpers after `_paper_arxiv_id()`:

```python
_DIRECT_ITEM_SPLIT_RE = re.compile(r"[\n;,]+")
_DIRECT_ITEM_PREFIX_RE = re.compile(r"^\s*(?:[-*+]\s+|\d+[.)]\s+)")


def _clean_direct_input_item(value: str) -> str:
    cleaned = _DIRECT_ITEM_PREFIX_RE.sub("", value.strip())
    return cleaned.strip().strip("`").strip()


def _split_direct_input_items(input_value: str) -> list[str]:
    items: list[str] = []
    for part in _DIRECT_ITEM_SPLIT_RE.split(input_value):
        cleaned = _clean_direct_input_item(part)
        if cleaned:
            items.append(cleaned)
    return items
```

- [ ] **Step 4: Run the parsing tests**

Run:

```bash
uv run pytest tests/test_v3_ingest.py::V3IngestTest::test_split_direct_input_items_handles_agent_batch_formats tests/test_v3_ingest.py::V3IngestTest::test_split_direct_input_items_keeps_single_url_intact -v
```

Expected: PASS.

- [ ] **Step 5: Commit Task 2**

Run:

```bash
git add server/v3_ingest.py tests/test_v3_ingest.py
git commit -m "feat: parse batch ingest inputs"
```

---

### Task 3: Implement Batch Direct Ingest

**Files:**
- Modify: `tests/test_v3_ingest.py`
- Modify: `server/v3_ingest.py`

- [ ] **Step 1: Add failing tests for bare ID and multi-item direct ingest**

Add these test methods inside `class V3IngestTest(unittest.TestCase)` in `tests/test_v3_ingest.py`:

```python
def test_direct_input_accepts_bare_arxiv_id(self) -> None:
    with tempfile.TemporaryDirectory() as tmpdir:
        captured = _cleaned_doc("Bare ID Paper", "# Bare ID Paper\n\nBody.")

        with patch("server.v3_ingest.get_vault_path", return_value=tmpdir):
            with patch("server.v3_ingest.ensure_v3_layout", return_value={"created": []}):
                with patch(
                    "server.v3_ingest.fetch_arxiv_record",
                    new=AsyncMock(
                        return_value={
                            "paper_id": "arxiv:1706.03762",
                            "title": "Bare ID Paper",
                            "arxiv_id": "1706.03762",
                            "authors": ["Ashish Vaswani"],
                            "year": 2017,
                        }
                    ),
                ) as fetch_mock:
                    with patch("server.v3_ingest.capture_arxiv_source", new=AsyncMock(return_value=captured)):
                        from server.v3_ingest import ingest_and_read_v3

                        result = asyncio.run(ingest_and_read_v3("1706.03762"))

    self.assertEqual(fetch_mock.await_count, 1)
    self.assertEqual(result["captured_count"], 1)
    self.assertEqual(result["error_count"], 0)
    self.assertEqual(result["items"][0]["input"], "1706.03762")
    self.assertEqual(result["items"][0]["paper_id"], "arxiv:1706.03762")

def test_direct_input_ingests_multiple_resolved_arxiv_items(self) -> None:
    with tempfile.TemporaryDirectory() as tmpdir:
        docs = {
            "2405.12213": _cleaned_doc("First Paper", "# First Paper\n\nBody."),
            "1706.03762": _cleaned_doc("Second Paper", "# Second Paper\n\nBody."),
        }

        async def fake_fetch(arxiv_id: str):
            return {
                "paper_id": f"arxiv:{arxiv_id}",
                "title": "First Paper" if arxiv_id == "2405.12213" else "Second Paper",
                "arxiv_id": arxiv_id,
                "authors": ["Ada Lovelace"],
                "year": 2025,
            }

        async def fake_capture(paper: dict, **_kwargs):
            return docs[paper["arxiv_id"]]

        raw_input = """
        - https://arxiv.org/abs/2405.12213
        - 1706.03762
        """

        with patch("server.v3_ingest.get_vault_path", return_value=tmpdir):
            with patch("server.v3_ingest.ensure_v3_layout", return_value={"created": []}):
                with patch("server.v3_ingest.fetch_arxiv_record", new=AsyncMock(side_effect=fake_fetch)):
                    with patch("server.v3_ingest.capture_arxiv_source", new=AsyncMock(side_effect=fake_capture)):
                        from server.v3_ingest import ingest_and_read_v3

                        result = asyncio.run(ingest_and_read_v3(raw_input))

    self.assertEqual(result["captured_count"], 2)
    self.assertEqual(result["error_count"], 0)
    self.assertEqual([item["paper_id"] for item in result["items"]], ["arxiv:2405.12213", "arxiv:1706.03762"])
    self.assertEqual(result["errors"], [])
```

- [ ] **Step 2: Add failing tests for mixed invalid input and duplicate IDs**

Add these test methods inside `class V3IngestTest(unittest.TestCase)` in `tests/test_v3_ingest.py`:

```python
def test_direct_input_reports_invalid_items_without_stopping_batch(self) -> None:
    with tempfile.TemporaryDirectory() as tmpdir:
        captured = _cleaned_doc("Good Paper", "# Good Paper\n\nBody.")

        with patch("server.v3_ingest.get_vault_path", return_value=tmpdir):
            with patch("server.v3_ingest.ensure_v3_layout", return_value={"created": []}):
                with patch(
                    "server.v3_ingest.fetch_arxiv_record",
                    new=AsyncMock(
                        return_value={
                            "paper_id": "arxiv:2405.12213",
                            "title": "Good Paper",
                            "arxiv_id": "2405.12213",
                            "authors": ["Ada Lovelace"],
                            "year": 2024,
                        }
                    ),
                ):
                    with patch("server.v3_ingest.capture_arxiv_source", new=AsyncMock(return_value=captured)):
                        from server.v3_ingest import ingest_and_read_v3

                        result = asyncio.run(
                            ingest_and_read_v3("openvla, https://arxiv.org/abs/2405.12213")
                        )

    self.assertEqual(result["captured_count"], 1)
    self.assertEqual(result["error_count"], 1)
    self.assertEqual(result["items"][0]["paper_id"], "arxiv:2405.12213")
    self.assertEqual(result["errors"][0]["input"], "openvla")
    self.assertIn("resolved to an arXiv", result["errors"][0]["error"])
    self.assertNotIn("error", result)

def test_direct_input_skips_duplicate_arxiv_ids_in_same_batch(self) -> None:
    with tempfile.TemporaryDirectory() as tmpdir:
        captured = _cleaned_doc("Duplicate Paper", "# Duplicate Paper\n\nBody.")

        with patch("server.v3_ingest.get_vault_path", return_value=tmpdir):
            with patch("server.v3_ingest.ensure_v3_layout", return_value={"created": []}):
                with patch(
                    "server.v3_ingest.fetch_arxiv_record",
                    new=AsyncMock(
                        return_value={
                            "paper_id": "arxiv:2405.12213",
                            "title": "Duplicate Paper",
                            "arxiv_id": "2405.12213",
                            "authors": ["Ada Lovelace"],
                            "year": 2024,
                        }
                    ),
                ) as fetch_mock:
                    with patch(
                        "server.v3_ingest.capture_arxiv_source",
                        new=AsyncMock(return_value=captured),
                    ) as capture_mock:
                        from server.v3_ingest import ingest_and_read_v3

                        result = asyncio.run(
                            ingest_and_read_v3(
                                "https://arxiv.org/abs/2405.12213, 2405.12213, https://arxiv.org/pdf/2405.12213.pdf"
                            )
                        )

    self.assertEqual(fetch_mock.await_count, 1)
    self.assertEqual(capture_mock.await_count, 1)
    self.assertEqual(result["captured_count"], 1)
    self.assertEqual(result["error_count"], 0)
    self.assertEqual(result["skipped_duplicates"], ["2405.12213", "2405.12213"])
```

- [ ] **Step 3: Run the new ingest tests and verify they fail**

Run:

```bash
uv run pytest \
  tests/test_v3_ingest.py::V3IngestTest::test_direct_input_accepts_bare_arxiv_id \
  tests/test_v3_ingest.py::V3IngestTest::test_direct_input_ingests_multiple_resolved_arxiv_items \
  tests/test_v3_ingest.py::V3IngestTest::test_direct_input_reports_invalid_items_without_stopping_batch \
  tests/test_v3_ingest.py::V3IngestTest::test_direct_input_skips_duplicate_arxiv_ids_in_same_batch \
  -v
```

Expected: FAIL because direct ingest still handles only one input and rejects bare IDs before Task 1 is implemented.

- [ ] **Step 4: Add result helper functions to `server/v3_ingest.py`**

Add these helpers after `_approved_error()`:

```python
_DIRECT_RESOLUTION_ERROR = "Item must be resolved to an arXiv URL, arXiv ID, or arXiv DOI before capture."


def _direct_item_error(input_item: str, error: Exception | str) -> dict[str, str]:
    message = str(error)
    return {
        "input": input_item,
        "error": message,
    }


def _direct_batch_result(
    items: list[dict[str, Any]],
    errors: list[dict[str, str]],
    skipped_duplicates: list[str],
) -> dict[str, Any]:
    return {
        "items": items,
        "errors": errors,
        "captured_count": len(items),
        "error_count": len(errors),
        "skipped_duplicates": skipped_duplicates,
    }
```

- [ ] **Step 5: Replace the non-approved branch in `ingest_and_read_v3`**

In `server/v3_ingest.py`, replace the code from:

```python
    source_url = input_value
    arxiv_id = extract_arxiv_id(source_url)
    if not arxiv_id:
        return {"error": "Direct URL must be an arXiv URL or arXiv DOI"}

    paper = dict(await fetch_arxiv_record(arxiv_id) or {})
    paper["arxiv_id"] = str(paper.get("arxiv_id") or arxiv_id).strip()
    paper["paper_id"] = str(paper.get("paper_id") or paper_id(paper)).strip()
    if not paper["paper_id"]:
        paper["paper_id"] = paper_id(paper)
    paper["title"] = str(paper.get("title") or f"arXiv {arxiv_id}").strip()

    try:
        capture = await _capture_raw_evidence(paper, source_url)
        raw_path = _write_raw_evidence(vault_path, capture)
    except Exception as exc:
        return {
            "error": str(exc),
            "paper_id": str(paper.get("paper_id") or ""),
            "title": str(paper.get("title") or ""),
            "source_url": source_url,
        }
    return {
        "items": [
            {
                "paper_id": capture["paper_id"],
                "title": capture["title"],
                "path": str(raw_path),
                "markdown": capture["markdown"],
                "source_url": capture["source_url"],
            }
        ]
    }
```

with:

```python
    input_items = _split_direct_input_items(input_value)
    items: list[dict[str, Any]] = []
    errors: list[dict[str, str]] = []
    skipped_duplicates: list[str] = []
    seen_arxiv_ids: set[str] = set()

    for input_item in input_items:
        arxiv_id = extract_arxiv_id(input_item)
        if not arxiv_id:
            errors.append(_direct_item_error(input_item, _DIRECT_RESOLUTION_ERROR))
            continue
        if arxiv_id in seen_arxiv_ids:
            skipped_duplicates.append(arxiv_id)
            continue
        seen_arxiv_ids.add(arxiv_id)

        source_url = input_item
        if source_url == arxiv_id:
            source_url = f"https://arxiv.org/abs/{arxiv_id}"

        paper = dict(await fetch_arxiv_record(arxiv_id) or {})
        paper["arxiv_id"] = str(paper.get("arxiv_id") or arxiv_id).strip()
        paper["paper_id"] = str(paper.get("paper_id") or paper_id(paper)).strip()
        if not paper["paper_id"]:
            paper["paper_id"] = paper_id(paper)
        paper["title"] = str(paper.get("title") or f"arXiv {arxiv_id}").strip()

        try:
            capture = await _capture_raw_evidence(paper, source_url)
            raw_path = _write_raw_evidence(vault_path, capture)
        except Exception as exc:
            error = {
                "input": input_item,
                "paper_id": str(paper.get("paper_id") or ""),
                "title": str(paper.get("title") or ""),
                "source_url": source_url,
                "error": str(exc),
            }
            errors.append(error)
            continue
        items.append(
            {
                "input": input_item,
                "paper_id": capture["paper_id"],
                "title": capture["title"],
                "path": str(raw_path),
                "markdown": capture["markdown"],
                "source_url": capture["source_url"],
            }
        )

    result = _direct_batch_result(items, errors, skipped_duplicates)
    if len(input_items) == 1 and errors and not items:
        result["error"] = errors[0]["error"]
        if "paper_id" in errors[0]:
            result["paper_id"] = errors[0].get("paper_id", "")
            result["title"] = errors[0].get("title", "")
            result["source_url"] = errors[0].get("source_url", input_items[0])
    return result
```

- [ ] **Step 6: Run the focused ingest tests**

Run:

```bash
uv run pytest \
  tests/test_v3_ingest.py::V3IngestTest::test_direct_input_accepts_bare_arxiv_id \
  tests/test_v3_ingest.py::V3IngestTest::test_direct_input_ingests_multiple_resolved_arxiv_items \
  tests/test_v3_ingest.py::V3IngestTest::test_direct_input_reports_invalid_items_without_stopping_batch \
  tests/test_v3_ingest.py::V3IngestTest::test_direct_input_skips_duplicate_arxiv_ids_in_same_batch \
  tests/test_v3_ingest.py::V3IngestTest::test_direct_input_rejects_non_arxiv_url \
  tests/test_v3_ingest.py::V3IngestTest::test_direct_input_returns_structured_error_when_capture_fails \
  -v
```

Expected: PASS.

- [ ] **Step 7: Run all ingest tests**

Run:

```bash
uv run pytest tests/test_v3_ingest.py -v
```

Expected: PASS.

- [ ] **Step 8: Commit Task 3**

Run:

```bash
git add server/v3_ingest.py tests/test_v3_ingest.py
git commit -m "feat: batch ingest resolved arxiv inputs"
```

---

### Task 4: Update Agent Skill and User Docs

**Files:**
- Modify: `skills/paper-intake/SKILL.md`
- Modify: `commands/ingest.md`
- Modify: `docs/commands.md`
- Modify: `README.md`
- Test: `tests/test_v3_commands.py`

- [ ] **Step 1: Add documentation expectations to command tests**

Open `tests/test_v3_commands.py` and add assertions to the existing command documentation test that reads `commands/ingest.md`. If there is no focused ingest command test, add this standalone test:

```python
def test_ingest_command_documents_agent_resolved_batch_inputs() -> None:
    ingest_doc = Path("commands/ingest.md").read_text(encoding="utf-8")

    assert "agent resolves" in ingest_doc
    assert "multiple resolved arXiv" in ingest_doc
    assert "openvla" in ingest_doc
```

If `Path` is not already imported in that file, add:

```python
from pathlib import Path
```

- [ ] **Step 2: Run the documentation test and verify it fails**

Run:

```bash
uv run pytest tests/test_v3_commands.py -v
```

Expected: FAIL because `commands/ingest.md` still says direct ingest is only an arXiv URL or DOI and does not mention agent-resolved batch input.

- [ ] **Step 3: Update `skills/paper-intake/SKILL.md`**

Replace the direct-ingest wording in `skills/paper-intake/SKILL.md` with this content.

In the `Available Tools` table, change the `ingest_and_read` row to:

```markdown
| `ingest_and_read` | Capture approved inbox notes or one/many agent-resolved arXiv identities |
```

Replace the `Routing Decision` list with:

```markdown
1. User asked to ingest approvals: call `ingest_and_read(input_value="approved")`.
2. User provided arXiv URL(s), arXiv ID(s), or arXiv DOI value(s): call `ingest_and_read(input_value=...)` directly. Batch multiple resolved identifiers into one call when possible.
3. User provided title(s), acronym(s), alias(es), project name(s), or mixed natural paper references: the agent must resolve each reference to an arXiv URL first, then call `ingest_and_read` with the resolved arXiv identities. Do not ask for a second confirmation after resolving.
4. User asked for discovery without asking to ingest specific papers: call `discover_papers(query=...)`, then stop and tell the user to approve inbox stubs by adding `#approved` in the note body.
5. User asked whether something is already in the vault or wants to read local evidence: use QMD CLI directly, usually `qmd query` or `qmd get`.
6. User wants a canonical paper page after capture and reading: distill the returned raw evidence, then call `upsert_wiki_page(page_type="paper", ...)`.
```

Replace the direct-input bullet under `Ingest Rules` with:

```markdown
- `ingest_and_read(input_value=<identifier_or_batch>)` accepts one or many arXiv URLs, arXiv IDs, or arXiv DOI values.
- Natural references such as `openvla`, exact paper titles, project names, and acronyms are agent-resolved before MCP capture. If the agent cannot find a credible arXiv URL for a reference, report it as unresolved and do not include it in the tool call.
- Do not ask the user to confirm agent-resolved arXiv URLs before calling `ingest_and_read`.
```

- [ ] **Step 4: Update `commands/ingest.md`**

Replace the current body with:

```markdown
---
name: ingest
description: Ingest approved inbox items or agent-resolved arXiv identities
user_invocable: true
---

Use the v3 `ingest_and_read` tool to ingest raw evidence.

If the argument is `approved`, ingest inbox notes whose body contains a plain `#approved` marker.

Otherwise, the agent resolves user-provided paper references to arXiv identities first. The MCP call should receive one or multiple resolved arXiv URLs, arXiv IDs, or arXiv DOI values and capture those papers into `raw/evidence/`.

Examples:
- `/ingest approved`
- `/ingest https://arxiv.org/abs/2410.24164`
- `/ingest 10.48550/arxiv.2410.24164`
- `/ingest 1706.03762`
- `/ingest openvla, octo, diffusion policy` — agent resolves these names to multiple resolved arXiv identities, then calls `ingest_and_read` once

After write-heavy work, QMD refresh is a separate follow-up step rather than an implicit part of this command. Recommend `qmd update` after the current write round, and `qmd embed -f` if semantic retrieval must reflect the new state immediately.
```

- [ ] **Step 5: Update `docs/commands.md`**

In `docs/commands.md`, replace the `/ingest` details with:

```markdown
### `/ingest`

Use `/ingest approved` to ingest approved inbox notes.

For direct paper intake, the agent can accept arXiv URLs, arXiv IDs, arXiv DOI values, exact titles, acronyms, aliases, project names, or mixed multi-paper requests. Natural references are resolved by the agent to arXiv URLs before calling the MCP tool. The MCP tool captures only resolved arXiv identities.

Examples:

```text
/ingest approved
/ingest https://arxiv.org/abs/2410.24164
/ingest 10.48550/arxiv.2410.24164
/ingest 1706.03762
/ingest openvla, octo, diffusion policy
```
```

- [ ] **Step 6: Update `README.md`**

Replace the direct ingestion paragraph and examples in `README.md` with:

```markdown
Direct ingestion is also available. The agent can resolve paper titles, acronyms, aliases, project names, arXiv URLs, arXiv IDs, or arXiv DOI values to arXiv identities, then call the single intake tool:

```text
/ingest https://arxiv.org/abs/2410.24164
/ingest 10.48550/arxiv.2410.24164
/ingest 1706.03762
/ingest openvla, octo, diffusion policy
```
```

- [ ] **Step 7: Run command/doc tests**

Run:

```bash
uv run pytest tests/test_v3_commands.py tests/test_skill_inventory.py tests/test_no_retired_names.py -v
```

Expected: PASS.

- [ ] **Step 8: Commit Task 4**

Run:

```bash
git add skills/paper-intake/SKILL.md commands/ingest.md docs/commands.md README.md tests/test_v3_commands.py
git commit -m "docs: describe agent-resolved intake"
```

---

### Task 5: Final Verification

**Files:**
- Verify all changed files from Tasks 1-4.

- [ ] **Step 1: Run focused test suite**

Run:

```bash
uv run pytest tests/test_paper_utils.py tests/test_v3_ingest.py tests/test_v3_commands.py tests/test_skill_inventory.py tests/test_no_retired_names.py -v
```

Expected: PASS.

- [ ] **Step 2: Run broader test suite**

Run:

```bash
uv run pytest -q
```

Expected: PASS.

- [ ] **Step 3: Check changed files**

Run:

```bash
git status --short
git diff --stat HEAD
```

Expected: only intentional files changed since the last task commit, or a clean worktree if each task was committed.

- [ ] **Step 4: Manual behavior check with mocked reasoning boundary**

No live web search is required. Confirm the documented boundary by reading the skill:

```bash
rg -n "agent.*resolv|second confirmation|one or many|arXiv ID" skills/paper-intake/SKILL.md commands/ingest.md README.md docs/commands.md
```

Expected: docs clearly say natural references are resolved by the agent before MCP capture, and MCP receives resolved arXiv identities.

- [ ] **Step 5: Final commit if verification changed files**

If final verification required any fixes, commit them:

```bash
git add server/paper_utils.py server/v3_ingest.py tests/test_paper_utils.py tests/test_v3_ingest.py tests/test_v3_commands.py skills/paper-intake/SKILL.md commands/ingest.md docs/commands.md README.md
git commit -m "fix: finalize agent-resolved intake"
```

If `git status --short` is clean, do not create an empty commit.

---

## Self-Review

Spec coverage:

- One user-facing intake interface remains `ingest_and_read`: Tasks 3 and 4.
- Agent accepts natural references and resolves them before MCP capture: Task 4.
- Multi-paper requests in one turn: Tasks 2, 3, and 4.
- No second confirmation after agent resolution: Task 4.
- Raw evidence writes remain deterministic and arXiv-grounded: Task 3.
- Per-paper success and error details: Task 3.
- Non-goal that server is not a natural-language resolver: Task 4 documents it, Task 3 rejects unresolved items.
- Batch separators: Task 2.
- Existing `approved` behavior unchanged: Task 3 includes full ingest test run, Task 5 broader verification.

Placeholder scan:

- No `TBD`, `TODO`, or incomplete implementation markers are present.
- Each code-changing step includes concrete code.

Type consistency:

- Helper names are consistently `_split_direct_input_items`, `_direct_item_error`, and `_direct_batch_result`.
- Response fields are consistently `items`, `errors`, `captured_count`, `error_count`, and `skipped_duplicates`.
- Existing single-item compatibility is preserved with top-level `error`, `paper_id`, `title`, and `source_url` when applicable.
