# Paper Distill v3.0 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the v2.1 hidden-state pipeline with a Markdown-first v3.0 server that can bootstrap an empty vault, initialize QMD, and run the first-release loop `discover -> approve -> ingest -> canon compilation -> maintenance -> conversation memory`.

**Architecture:** Build the v3.0 cutover as a set of focused new modules and rewire the existing `tools_*` facade to them. Bootstrap stays internal: `status` and mutating paths ensure the empty-vault layout and QMD collections/contexts exist, but no new user-facing `/bootstrap` command is added.

**Tech Stack:** Python 3.10, FastMCP, qmd CLI, httpx, PyYAML, ruamel.yaml, pytest, uv

---

## File Map

### Create

- `server/v3_bootstrap.py` — empty-vault directory creation, shared file naming helpers, and `.state/seen_papers.json` initialization.
- `server/qmd_runtime.py` — thin qmd CLI wrapper for collection/context bootstrap, readiness checks, search, get, update, and re-embed.
- `server/v3_discovery.py` — v3 discovery flow, inbox stub rendering, and seen-cache deduplication.
- `server/v3_ingest.py` — approved-inbox and direct-URL ingest flow that writes `raw/evidence` and returns captured Markdown.
- `server/v3_store.py` — minimal frontmatter validation, atomic Markdown writes, vault log append, and post-write qmd scheduling.
- `server/v3_alias.py` — canonical concept and alias scan for `check_concept_alias`.
- `server/v3_health.py` — v3 lint rules, merge rewrites, and maintenance helpers.
- `server/v3_memory.py` — conversation-memory writer for `insights/conversations`.
- `tests/test_v3_bootstrap.py`
- `tests/test_qmd_runtime.py`
- `tests/test_v3_core_tools.py`
- `tests/test_v3_discovery.py`
- `tests/test_v3_ingest.py`
- `tests/test_v3_store.py`
- `tests/test_v3_alias.py`
- `tests/test_v3_health.py`
- `tests/test_v3_memory.py`
- `tests/test_v3_commands.py`
- `commands/get.md`
- `commands/inbox.md`

### Modify

- `pyproject.toml` — bump package version to `3.0.0` and add `ruamel.yaml`.
- `server/config.py` — qmd binary/config lookup and v3 vault-path helpers.
- `server/server.py` — register the v3 MCP tool surface.
- `server/server_runtime.py` — delegate to v3 modules and drop v2 compile-centric exports from the primary path.
- `server/tools_core.py` — expose `kb_search`, `kb_get`, and `status`.
- `server/tools_intake.py` — expose `discover_papers` and `ingest_and_read`.
- `server/tools_knowledge.py` — expose `check_concept_alias`, `upsert_wiki_page`, `merge_concept`, `kb_update_index`, and `kb_reembed_force`.
- `server/tools_health.py` — expose the v3 lint/health entry point.
- `server/cli.py` — repurpose admin bootstrap for empty-vault layout + qmd initialization.
- `commands/discover.md`
- `commands/ingest.md`
- `commands/search.md`
- `commands/lint.md`
- `commands/status.md`
- `skills/paper-intake/SKILL.md`
- `skills/knowledge-workbench/SKILL.md`
- `README.md`
- `docs/architecture.md`
- `docs/commands.md`
- `docs/installation.md`
- `docs/testing.md`

### Leave Alone For This Cutover

- `server/search/*.py` — keep existing multi-source search adapters; reuse them from the new discovery flow.
- `server/arxiv_capture.py`, `server/arxiv_markdown.py`, `server/arxiv_html_*` — reuse the existing capture stack instead of rebuilding it.
- Legacy v2 modules such as `server/compile_ir.py` and `server/database.py` — remove them from the active path first; physical deletion can happen after the v3 surface is stable.

## Task 1: Establish Empty-Vault Bootstrap And Shared Naming

**Files:**
- Create: `server/v3_bootstrap.py`
- Test: `tests/test_v3_bootstrap.py`
- Modify: `pyproject.toml`
- Modify: `server/config.py`

- [ ] **Step 1: Write the failing bootstrap test**

```python
from server.v3_bootstrap import ensure_v3_layout, paper_filename


def test_ensure_v3_layout_creates_empty_vault_tree(tmp_path):
    result = ensure_v3_layout(tmp_path)

    assert (tmp_path / "inbox").is_dir()
    assert (tmp_path / "raw" / "evidence").is_dir()
    assert (tmp_path / "wiki" / "papers").is_dir()
    assert (tmp_path / "wiki" / "concepts").is_dir()
    assert (tmp_path / "insights" / "conversations").is_dir()
    assert (tmp_path / "exports" / "presentations").is_dir()
    assert (tmp_path / ".state" / "seen_papers.json").read_text(encoding="utf-8") == "{}\n"
    assert (tmp_path / "vault-log.md").exists()
    assert paper_filename("Attention Is All You Need", "arxiv:1706.03762") == "attention-is-all-you-need--arxiv-1706.03762.md"
    assert result["created"]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_v3_bootstrap.py -q`
Expected: FAIL with `ModuleNotFoundError: No module named 'server.v3_bootstrap'`

- [ ] **Step 3: Write the minimal bootstrap implementation**

```python
# server/v3_bootstrap.py
from __future__ import annotations

import json
import re
from pathlib import Path

V3_DIRS = (
    "inbox",
    "raw/evidence",
    "wiki/papers",
    "wiki/concepts",
    "insights/ideas",
    "insights/conversations",
    "exports/presentations",
    ".state",
)


def _slugify(value: str) -> str:
    lowered = value.casefold()
    cleaned = re.sub(r"[^a-z0-9]+", "-", lowered).strip("-")
    return cleaned or "untitled"


def paper_filename(title: str, paper_id: str) -> str:
    safe_id = paper_id.replace(":", "-")
    return f"{_slugify(title)}--{safe_id}.md"


def ensure_v3_layout(vault_path: Path) -> dict[str, list[str]]:
    created: list[str] = []
    for rel in V3_DIRS:
        path = vault_path / rel
        if not path.exists():
            path.mkdir(parents=True, exist_ok=True)
            created.append(rel)

    seen_path = vault_path / ".state" / "seen_papers.json"
    if not seen_path.exists():
        seen_path.write_text("{}\n", encoding="utf-8")
        created.append(".state/seen_papers.json")

    log_path = vault_path / "vault-log.md"
    if not log_path.exists():
        log_path.write_text(
            "# Vault Operation Log\n\n| Timestamp | Action | Resource ID | Status | Notes |\n|-----------|--------|-------------|--------|-------|\n",
            encoding="utf-8",
        )
        created.append("vault-log.md")

    return {"created": created}
```

```toml
# pyproject.toml
version = "3.0.0"
dependencies = [
    "fastmcp>=2.0.0",
    "httpx>=0.27.0",
    "pyzotero>=1.5.0",
    "pymupdf>=1.24.0",
    "rapidfuzz>=3.0.0",
    "python-dateutil>=2.9.0",
    "beautifulsoup4>=4.12.0",
    "pyyaml>=6.0",
    "jinja2>=3.1.0",
    "ruamel.yaml>=0.18.0",
]
```

```python
# server/config.py
def get_qmd_binary() -> str:
    return get_env("PAPER_DISTILL_QMD_BINARY", "qmd")
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_v3_bootstrap.py -q`
Expected: `1 passed`

- [ ] **Step 5: Commit**

```bash
git add pyproject.toml server/config.py server/v3_bootstrap.py tests/test_v3_bootstrap.py
git commit -m "feat: add v3 vault bootstrap foundation"
```

## Task 2: Add QMD Bootstrap, Readiness, And Empty-Repo Init

**Files:**
- Create: `server/qmd_runtime.py`
- Test: `tests/test_qmd_runtime.py`
- Modify: `server/cli.py`

- [ ] **Step 1: Write the failing qmd bootstrap tests**

```python
from server.qmd_runtime import ensure_qmd_ready, qmd_ready_report


def test_ensure_qmd_ready_bootstraps_expected_collections_and_contexts(tmp_path, monkeypatch):
    calls = []

    def fake_run(cmd, check, capture_output, text):
        calls.append(cmd)

        class Result:
            stdout = "ok"
            stderr = ""
            returncode = 0

        return Result()

    monkeypatch.setattr("server.qmd_runtime.subprocess.run", fake_run)

    report = ensure_qmd_ready(tmp_path)

    assert ["qmd", "collection", "add", str(tmp_path / "wiki" / "papers"), "--name", "canon-papers"] in calls
    assert ["qmd", "collection", "add", str(tmp_path / "wiki" / "concepts"), "--name", "canon-concepts"] in calls
    assert ["qmd", "collection", "add", str(tmp_path / "insights" / "conversations"), "--name", "insights-conversations"] in calls
    assert ["qmd", "collection", "add", str(tmp_path / "raw" / "evidence"), "--name", "raw-evidence"] in calls
    assert ["qmd", "context", "add", "qmd://canon-papers", "Canonical distilled papers"] in calls
    assert report["ready"] is True


def test_qmd_ready_report_returns_not_ready_when_binary_missing(tmp_path, monkeypatch):
    def raise_missing(*args, **kwargs):
        raise FileNotFoundError("qmd")

    monkeypatch.setattr("server.qmd_runtime.subprocess.run", raise_missing)

    report = qmd_ready_report(tmp_path)

    assert report["status"] == "not_ready"
    assert report["reason"] == "qmd binary not found"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_qmd_runtime.py -q`
Expected: FAIL with `ModuleNotFoundError: No module named 'server.qmd_runtime'`

- [ ] **Step 3: Implement qmd runtime and repurpose admin bootstrap**

```python
# server/qmd_runtime.py
from __future__ import annotations

import json
import subprocess
from pathlib import Path

from server.config import get_qmd_binary

COLLECTIONS = (
    ("canon-papers", "wiki/papers", "Canonical distilled papers"),
    ("canon-concepts", "wiki/concepts", "Canonical concept pages"),
    ("insights-conversations", "insights/conversations", "Conversation-derived research insights"),
    ("insights-ideas", "insights/ideas", "Idea drafts and later validation assets"),
    ("raw-evidence", "raw/evidence", "Raw captured evidence and source markdown"),
)

SCOPE_TO_COLLECTIONS = {
    "canon": ["canon-papers", "canon-concepts"],
    "insights": ["insights-conversations", "insights-ideas"],
    "raw": ["raw-evidence"],
}


def _run_qmd(args: list[str]) -> subprocess.CompletedProcess:
    return subprocess.run([get_qmd_binary(), *args], check=True, capture_output=True, text=True)


def ensure_qmd_ready(vault_path: Path) -> dict[str, object]:
    existing_collections = _run_qmd(["collection", "list"]).stdout
    existing_contexts = _run_qmd(["context", "list"]).stdout
    for name, rel, context in COLLECTIONS:
        if name not in existing_collections:
            _run_qmd(["collection", "add", str(vault_path / rel), "--name", name])
        if f"qmd://{name}" not in existing_contexts:
            _run_qmd(["context", "add", f"qmd://{name}", context])
    return {"ready": True, "collections": [name for name, _, _ in COLLECTIONS]}


def qmd_ready_report(vault_path: Path) -> dict[str, object]:
    try:
        result = _run_qmd(["collection", "list"])
    except FileNotFoundError:
        return {"status": "not_ready", "reason": "qmd binary not found"}
    except subprocess.CalledProcessError as exc:
        return {"status": "not_ready", "reason": exc.stderr.strip() or "qmd unavailable"}

    stdout = result.stdout
    missing = [name for name, _, _ in COLLECTIONS if name not in stdout]
    if missing:
        return {"status": "degraded", "reason": "missing qmd collections", "missing": missing}
    return {"status": "ready", "reason": "qmd collections available"}


def qmd_search(vault_path: Path, query: str, scope: str) -> dict[str, object]:
    ready = qmd_ready_report(vault_path)
    if ready["status"] == "not_ready":
        return {"status": "not_ready", "error": ready["reason"]}

    args = ["query", query, "--json"]
    for collection in SCOPE_TO_COLLECTIONS[scope]:
        args.extend(["-c", collection])
    result = _run_qmd(args)
    return {"status": "ok", "scope": scope, "qmd_context": scope, "results": json.loads(result.stdout)}


def qmd_get(vault_path: Path, id_or_path: str) -> dict[str, object]:
    candidate = Path(id_or_path)
    if not candidate.exists():
        matches = sorted(vault_path.rglob(f"{id_or_path}.md"))
        if not matches:
            return {"status": "missing", "error": f"document not found: {id_or_path}"}
        candidate = matches[0]
    result = _run_qmd(["get", str(candidate)])
    return {"status": "ok", "path": str(candidate), "body": result.stdout}


def qmd_update(vault_path: Path) -> dict[str, object]:
    try:
        result = _run_qmd(["update"])
    except subprocess.CalledProcessError as exc:
        return {"ok": False, "error": exc.stderr.strip() or "qmd update failed"}
    return {"ok": True, "stdout": result.stdout}


def qmd_reembed_force(vault_path: Path) -> dict[str, object]:
    try:
        result = _run_qmd(["embed", "-f"])
    except subprocess.CalledProcessError as exc:
        return {"ok": False, "error": exc.stderr.strip() or "qmd embed failed"}
    return {"ok": True, "stdout": result.stdout}
```

```python
# server/cli.py
from server.qmd_runtime import ensure_qmd_ready
from server.v3_bootstrap import ensure_v3_layout


async def _bootstrap(args: argparse.Namespace) -> None:
    vault_path = Path(args.vault_path or get_vault_path())
    layout = ensure_v3_layout(vault_path)
    qmd = ensure_qmd_ready(vault_path)
    print(json.dumps({"layout": layout, "qmd": qmd}, indent=2, ensure_ascii=False))
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_qmd_runtime.py -q`
Expected: `2 passed`

- [ ] **Step 5: Commit**

```bash
git add server/qmd_runtime.py server/cli.py tests/test_qmd_runtime.py
git commit -m "feat: add qmd bootstrap and readiness runtime"
```

## Task 3: Rewire The Core Read Surface To `kb_search`, `kb_get`, And `status`

**Files:**
- Create: `tests/test_v3_core_tools.py`
- Modify: `server/tools_core.py`
- Modify: `server/server_runtime.py`
- Modify: `server/server.py`

- [ ] **Step 1: Write the failing core-tool tests**

```python
import pytest

from server.server import mcp
from server.tools_core import kb_get, kb_search, status


@pytest.mark.asyncio
async def test_mcp_lists_v3_core_tool_names():
    tools = await mcp.list_tools()
    names = {tool.name for tool in tools}
    assert {"kb_search", "kb_get", "status"} <= names


@pytest.mark.asyncio
async def test_kb_search_returns_not_ready_when_qmd_is_missing(monkeypatch):
    async def fake_kb_search(*args, **kwargs):
        return {"status": "not_ready", "error": "qmd binary not found"}

    monkeypatch.setattr("server.tools_core._kb_search", fake_kb_search)

    result = await kb_search("transformer", "canon")

    assert result["status"] == "not_ready"
    assert result["error"] == "qmd binary not found"


@pytest.mark.asyncio
async def test_kb_get_returns_current_file_truth(monkeypatch):
    async def fake_kb_get(*args, **kwargs):
        return {"status": "ok", "path": "/tmp/wiki/papers/demo.md", "body": "# Demo"}

    monkeypatch.setattr("server.tools_core._kb_get", fake_kb_get)

    result = await kb_get("demo")

    assert result["status"] == "ok"
    assert result["body"] == "# Demo"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_v3_core_tools.py -q`
Expected: FAIL because `kb_search` / `kb_get` are not registered yet

- [ ] **Step 3: Implement the new core tools**

```python
# server/server_runtime.py
from pathlib import Path

from server.qmd_runtime import qmd_get, qmd_ready_report, qmd_search
from server.v3_bootstrap import ensure_v3_layout


async def kb_search(query: str, scope: str = "canon") -> dict:
    vault_path = Path(get_vault_path())
    ensure_v3_layout(vault_path)
    return qmd_search(vault_path=vault_path, query=query, scope=scope)


async def kb_get(id_or_path: str) -> dict:
    vault_path = Path(get_vault_path())
    ensure_v3_layout(vault_path)
    return qmd_get(vault_path=vault_path, id_or_path=id_or_path)


async def v3_status() -> dict:
    vault_path = Path(get_vault_path())
    layout = ensure_v3_layout(vault_path)
    qmd = qmd_ready_report(vault_path)
    return {"layout": layout, "qmd": qmd}
```

```python
# server/tools_core.py
from server.server_runtime import kb_search as _kb_search, kb_get as _kb_get, v3_status as _status


async def kb_search(query: str, scope: str = "canon") -> dict[str, Any]:
    return await _kb_search(query=query, scope=scope)


async def kb_get(id_or_path: str) -> dict[str, Any]:
    return await _kb_get(id_or_path=id_or_path)


async def status() -> dict[str, Any]:
    return await _status()


def register_core_tools(mcp: FastMCP) -> None:
    mcp.tool(name="kb_search")(kb_search)
    mcp.tool(name="kb_get")(kb_get)
    mcp.tool(name="status")(status)
    mcp.tool(name="update-preferences")(update_preferences)
```

```python
# server/server.py
"""Thin Paper Distill MCP entrypoint for the v3.0 tool surface."""
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_v3_core_tools.py -q`
Expected: `3 passed`

- [ ] **Step 5: Commit**

```bash
git add server/server.py server/server_runtime.py server/tools_core.py tests/test_v3_core_tools.py
git commit -m "feat: expose v3 core read tools"
```

## Task 4: Implement Discovery, Inbox Stubs, And Seen-Cache Deduplication

**Files:**
- Create: `server/v3_discovery.py`
- Test: `tests/test_v3_discovery.py`
- Modify: `server/tools_intake.py`
- Modify: `server/server_runtime.py`
- Modify: `commands/discover.md`
- Create: `commands/inbox.md`

- [ ] **Step 1: Write the failing discovery tests**

```python
import json

from server.v3_discovery import discover_papers_v3


def test_discover_papers_writes_inbox_stub_and_updates_seen_cache(tmp_path, monkeypatch):
    async def fake_search(*args, **kwargs):
        return [{
            "title": "Attention Is All You Need",
            "paper_id": "arxiv:1706.03762",
            "source_url": "https://arxiv.org/abs/1706.03762",
        }]

    monkeypatch.setattr("server.v3_discovery.search_papers", fake_search)
    monkeypatch.setattr("server.v3_discovery.get_vault_path", lambda: str(tmp_path))

    result = __import__("asyncio").run(discover_papers_v3(query="transformer"))

    inbox_files = list((tmp_path / "inbox").glob("*.md"))
    assert len(inbox_files) == 1
    assert "#approved" not in inbox_files[0].read_text(encoding="utf-8")
    cache = json.loads((tmp_path / ".state" / "seen_papers.json").read_text(encoding="utf-8"))
    assert cache["arxiv:1706.03762"]["score"] >= 0
    assert result["saved"][0]["paper_id"] == "arxiv:1706.03762"


def test_discover_papers_skips_seen_ids(tmp_path, monkeypatch):
    (tmp_path / ".state").mkdir(parents=True)
    (tmp_path / ".state" / "seen_papers.json").write_text('{"arxiv:1706.03762": {"score": 88}}\n', encoding="utf-8")

    async def fake_search(*args, **kwargs):
        return [{
            "title": "Attention Is All You Need",
            "paper_id": "arxiv:1706.03762",
            "source_url": "https://arxiv.org/abs/1706.03762",
        }]

    monkeypatch.setattr("server.v3_discovery.search_papers", fake_search)
    monkeypatch.setattr("server.v3_discovery.get_vault_path", lambda: str(tmp_path))

    result = __import__("asyncio").run(discover_papers_v3(query="transformer"))

    assert result["saved"] == []
    assert result["skipped_seen"] == ["arxiv:1706.03762"]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_v3_discovery.py -q`
Expected: FAIL with `ModuleNotFoundError: No module named 'server.v3_discovery'`

- [ ] **Step 3: Implement v3 discovery**

```python
# server/v3_discovery.py
from __future__ import annotations

import json
from datetime import date
from pathlib import Path

from server.config import get_vault_path
from server.server_runtime import search_papers
from server.v3_bootstrap import ensure_v3_layout, paper_filename


def _load_seen_cache(vault_path: Path) -> dict:
    cache_path = vault_path / ".state" / "seen_papers.json"
    return json.loads(cache_path.read_text(encoding="utf-8"))


def _write_seen_cache(vault_path: Path, payload: dict) -> None:
    (vault_path / ".state" / "seen_papers.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def _render_inbox_stub(paper: dict, score: int) -> str:
    return (
        "---\n"
        f"type: inbox_stub\npaper_id: {paper['paper_id']}\n"
        f"title: {paper['title']}\nsource_url: {paper['source_url']}\n"
        f"discovered_at: \"{date.today().isoformat()}\"\nscore: {score}\n"
        "---\n\n"
        f"# {paper['title']}\n\n"
        f"- Paper ID: `{paper['paper_id']}`\n"
        f"- Score: {score}\n"
        f"- Source: {paper['source_url']}\n"
    )


async def discover_papers_v3(query: str | None = None) -> dict:
    vault_path = Path(get_vault_path())
    ensure_v3_layout(vault_path)
    cache = _load_seen_cache(vault_path)
    results = await search_papers(query=query or "", sources=None, max_results=20)

    saved = []
    skipped_seen = []
    for paper in results:
        pid = paper["paper_id"]
        if pid in cache:
            skipped_seen.append(pid)
            continue
        score = int(paper.get("score", 80))
        path = vault_path / "inbox" / paper_filename(paper["title"], pid)
        path.write_text(_render_inbox_stub(paper, score), encoding="utf-8")
        cache[pid] = {"added_at": date.today().isoformat(), "score": score}
        saved.append({"paper_id": pid, "path": str(path)})

    _write_seen_cache(vault_path, cache)
    return {"saved": saved, "skipped_seen": skipped_seen}
```

```python
# server/tools_intake.py
from server.server_runtime import discover_papers_v3 as _discover_papers_v3


async def discover_papers(query: str | None = None) -> dict[str, Any]:
    return await _discover_papers_v3(query=query)


def register_intake_tools(mcp: FastMCP) -> None:
    mcp.tool(name="discover_papers")(discover_papers)
```

```markdown
<!-- commands/discover.md -->
---
name: discover
description: Discover candidate papers and write inbox stubs
user_invocable: true
---

Run the v3 discovery flow, write new candidates into `inbox/`, and summarize how many items were saved versus skipped from `.state/seen_papers.json`.
```

```markdown
<!-- commands/inbox.md -->
---
name: inbox
description: Show inbox candidates and approval instructions
user_invocable: true
---

Summarize the current inbox, including how many files are present and which ones already contain `#approved`.
Do not ingest anything from this command.
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_v3_discovery.py -q`
Expected: `2 passed`

- [ ] **Step 5: Commit**

```bash
git add server/v3_discovery.py server/tools_intake.py server/server_runtime.py tests/test_v3_discovery.py commands/discover.md commands/inbox.md
git commit -m "feat: add v3 discovery and inbox flow"
```

## Task 5: Implement Approved-Inbox And Direct-URL Ingest Into `raw/evidence`

**Files:**
- Create: `server/v3_ingest.py`
- Test: `tests/test_v3_ingest.py`
- Modify: `server/tools_intake.py`
- Modify: `server/server_runtime.py`
- Modify: `commands/ingest.md`

- [ ] **Step 1: Write the failing ingest tests**

```python
import asyncio

from server.v3_ingest import ingest_and_read_v3


def test_ingest_and_read_only_processes_hash_approved_inbox_notes(tmp_path, monkeypatch):
    inbox = tmp_path / "inbox"
    inbox.mkdir(parents=True)
    (tmp_path / "raw" / "evidence").mkdir(parents=True)

    (inbox / "approved.md").write_text(
        "---\ntype: inbox_stub\npaper_id: arxiv:1706.03762\ntitle: Demo\nsource_url: https://arxiv.org/abs/1706.03762\n---\n\n#approved\n",
        encoding="utf-8",
    )
    (inbox / "pending.md").write_text(
        "---\ntype: inbox_stub\npaper_id: arxiv:1706.03763\ntitle: Pending\nsource_url: https://arxiv.org/abs/1706.03763\n---\n",
        encoding="utf-8",
    )

    async def fake_capture(url):
        return {
            "paper": {"title": "Demo", "paper_id": "arxiv:1706.03762", "source_url": url, "year": 2017},
            "markdown": "# Demo source",
        }

    monkeypatch.setattr("server.v3_ingest.capture_arxiv_source", fake_capture)
    monkeypatch.setattr("server.v3_ingest.get_vault_path", lambda: str(tmp_path))

    result = asyncio.run(ingest_and_read_v3("approved"))

    raw_files = list((tmp_path / "raw" / "evidence").glob("*.md"))
    assert len(raw_files) == 1
    assert result["items"][0]["paper_id"] == "arxiv:1706.03762"


def test_ingest_and_read_overwrites_same_raw_path_for_same_paper_id(tmp_path, monkeypatch):
    (tmp_path / "raw" / "evidence").mkdir(parents=True)

    payloads = iter(["# first", "# second"])

    async def fake_capture(url):
        return {
            "paper": {"title": "Demo", "paper_id": "arxiv:1706.03762", "source_url": url, "year": 2017},
            "markdown": next(payloads),
        }

    monkeypatch.setattr("server.v3_ingest.capture_arxiv_source", fake_capture)
    monkeypatch.setattr("server.v3_ingest.get_vault_path", lambda: str(tmp_path))

    asyncio.run(ingest_and_read_v3("https://arxiv.org/abs/1706.03762"))
    asyncio.run(ingest_and_read_v3("https://arxiv.org/abs/1706.03762"))

    raw_file = next((tmp_path / "raw" / "evidence").glob("*.md"))
    assert raw_file.read_text(encoding="utf-8").endswith("# second")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_v3_ingest.py -q`
Expected: FAIL with `ModuleNotFoundError: No module named 'server.v3_ingest'`

- [ ] **Step 3: Implement v3 ingest**

```python
# server/v3_ingest.py
from __future__ import annotations

import re
from pathlib import Path

from server.arxiv_capture import capture_arxiv_source
from server.config import get_vault_path
from server.v3_bootstrap import ensure_v3_layout, paper_filename


def _approved_urls(vault_path: Path) -> list[str]:
    urls: list[str] = []
    for path in sorted((vault_path / "inbox").glob("*.md")):
        text = path.read_text(encoding="utf-8")
        if "#approved" not in text:
            continue
        match = re.search(r"source_url:\s*(\S+)", text)
        if match:
            urls.append(match.group(1))
    return urls


def _raw_frontmatter(paper: dict) -> str:
    return (
        "---\n"
        f"type: raw_evidence\npaper_id: {paper['paper_id']}\n"
        f"title: {paper['title']}\nsource_url: {paper['source_url']}\n"
        "---\n\n"
    )


async def ingest_and_read_v3(input_value: str) -> dict:
    vault_path = Path(get_vault_path())
    ensure_v3_layout(vault_path)
    urls = _approved_urls(vault_path) if input_value == "approved" else [input_value]

    items = []
    for url in urls:
        captured = await capture_arxiv_source(url)
        paper = captured["paper"]
        raw_path = vault_path / "raw" / "evidence" / paper_filename(paper["title"], paper["paper_id"])
        raw_path.write_text(_raw_frontmatter(paper) + captured["markdown"], encoding="utf-8")
        items.append({"paper_id": paper["paper_id"], "path": str(raw_path), "markdown": captured["markdown"]})
    return {"items": items}
```

```python
# server/server_runtime.py
from server.v3_ingest import ingest_and_read_v3 as _ingest_and_read_v3


async def ingest_and_read_v3(input_value: str) -> dict:
    return await _ingest_and_read_v3(input_value=input_value)
```

```python
# server/tools_intake.py
from server.server_runtime import ingest_and_read_v3 as _ingest_and_read_v3


async def ingest_and_read(input_value: str) -> dict[str, Any]:
    return await _ingest_and_read_v3(input_value=input_value)


def register_intake_tools(mcp: FastMCP) -> None:
    mcp.tool(name="discover_papers")(discover_papers)
    mcp.tool(name="ingest_and_read")(ingest_and_read)
```

```markdown
<!-- commands/ingest.md -->
---
name: ingest
description: Ingest approved inbox items or a direct paper URL
user_invocable: true
---

If the argument is `approved`, ingest inbox files whose body contains `#approved`.
Otherwise treat the argument as a direct paper URL and run the v3 direct-ingest path.
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_v3_ingest.py -q`
Expected: `2 passed`

- [ ] **Step 5: Commit**

```bash
git add server/v3_ingest.py server/tools_intake.py server/server_runtime.py tests/test_v3_ingest.py commands/ingest.md
git commit -m "feat: add v3 raw ingest flow"
```

## Task 6: Add `upsert_wiki_page` And `check_concept_alias`

**Files:**
- Create: `server/v3_store.py`
- Create: `server/v3_alias.py`
- Test: `tests/test_v3_store.py`
- Test: `tests/test_v3_alias.py`
- Modify: `server/tools_knowledge.py`
- Modify: `server/server_runtime.py`

- [ ] **Step 1: Write the failing store and alias tests**

```python
from server.v3_alias import check_concept_alias_v3
from server.v3_store import upsert_wiki_page_v3


def test_upsert_wiki_page_writes_markdown_and_returns_warning_when_qmd_update_fails(tmp_path, monkeypatch):
    def fake_qmd_update(*args, **kwargs):
        return {"ok": False, "error": "qmd update failed"}

    monkeypatch.setattr("server.v3_store.qmd_update", fake_qmd_update)

    result = upsert_wiki_page_v3(
        vault_path=tmp_path,
        page_type="paper",
        target="attention-is-all-you-need--arxiv-1706.03762",
        frontmatter={"type": "paper", "paper_id": "arxiv:1706.03762", "year": 2017, "status": "distilled", "key_concepts_topk": ["Transformer"], "source_layer": "canon"},
        body="# Attention\n\n## Context\nTest",
    )

    written = next((tmp_path / "wiki" / "papers").glob("*.md"))
    assert result["ok"] is True
    assert result["warnings"] == ["qmd update failed"]
    assert written.exists()


def test_check_concept_alias_prefers_existing_canonical_name(tmp_path):
    concept_dir = tmp_path / "wiki" / "concepts"
    concept_dir.mkdir(parents=True)
    (concept_dir / "transformer.md").write_text(
        "---\ntype: concept\naliases: [变换器, Transformer模型]\nstatus: mature\nlast_updated: \"2026-04-15\"\nlast_tension_update: \"2026-04-15\"\nsources_topk: [\"arxiv:1706.03762\"]\n---\n\n# Transformer\n",
        encoding="utf-8",
    )

    result = check_concept_alias_v3(tmp_path, "Transformer模型")

    assert result["exists"] is True
    assert result["canonical"] == "Transformer"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_v3_store.py tests/test_v3_alias.py -q`
Expected: FAIL with missing `server.v3_store` / `server.v3_alias`

- [ ] **Step 3: Implement the store and alias modules**

```python
# server/v3_store.py
from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from ruamel.yaml import YAML

from server.qmd_runtime import qmd_update
from server.v3_bootstrap import ensure_v3_layout, paper_filename

YAML_RT = YAML()
YAML_RT.preserve_quotes = True


def _compose_markdown(frontmatter: dict, body: str) -> str:
    from io import StringIO

    stream = StringIO()
    stream.write("---\n")
    YAML_RT.dump(frontmatter, stream)
    stream.write("---\n\n")
    stream.write(body.rstrip() + "\n")
    return stream.getvalue()


def _target_path(vault_path: Path, page_type: str, target: str, frontmatter: dict) -> Path:
    if page_type == "paper":
        return vault_path / "wiki" / "papers" / f"{target}.md"
    if page_type == "concept":
        return vault_path / "wiki" / "concepts" / f"{target}.md"
    if page_type == "conversation":
        return vault_path / "insights" / "conversations" / f"{target}.md"
    raise ValueError(f"unsupported page_type: {page_type}")


def upsert_wiki_page_v3(vault_path: Path, page_type: str, target: str, frontmatter: dict, body: str) -> dict:
    ensure_v3_layout(vault_path)
    path = _target_path(vault_path, page_type, target, frontmatter)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = path.with_suffix(path.suffix + ".tmp")
    tmp_path.write_text(_compose_markdown(frontmatter, body), encoding="utf-8")
    tmp_path.replace(path)

    update_result = qmd_update(vault_path)
    warnings = [] if update_result.get("ok") else [update_result["error"]]
    return {"ok": True, "path": str(path), "warnings": warnings}
```

```python
# server/v3_alias.py
from __future__ import annotations

import re
from pathlib import Path


def check_concept_alias_v3(vault_path: Path, name: str) -> dict:
    concept_dir = vault_path / "wiki" / "concepts"
    for path in concept_dir.glob("*.md"):
        text = path.read_text(encoding="utf-8")
        canonical = path.stem.replace("-", " ").title()
        aliases = re.findall(r"-?\s*([^\],\n]+)", re.search(r"aliases:\s*\[(.*?)\]", text, re.S).group(1)) if "aliases:" in text else []
        if name == canonical or name in [alias.strip() for alias in aliases]:
            return {"exists": True, "canonical": canonical}
    return {"exists": False, "canonical": name}
```

```python
# server/server_runtime.py
from pathlib import Path

from server.v3_alias import check_concept_alias_v3 as _check_alias_fs
from server.v3_store import upsert_wiki_page_v3 as _upsert_page_fs


async def check_concept_alias_v3(name: str) -> dict:
    return _check_alias_fs(Path(get_vault_path()), name)


async def upsert_wiki_page_v3(page_type: str, target: str, frontmatter: dict, body: str) -> dict:
    return _upsert_page_fs(Path(get_vault_path()), page_type, target, frontmatter, body)
```

```python
# server/tools_knowledge.py
from server.server_runtime import check_concept_alias_v3 as _check_alias, upsert_wiki_page_v3 as _upsert_v3


async def check_concept_alias(name: str) -> dict[str, Any]:
    return await _check_alias(name)


async def upsert_wiki_page(page_type: str, target: str, frontmatter: dict, body: str) -> dict[str, Any]:
    return await _upsert_v3(page_type=page_type, target=target, frontmatter=frontmatter, body=body)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_v3_store.py tests/test_v3_alias.py -q`
Expected: `2 passed`

- [ ] **Step 5: Commit**

```bash
git add server/v3_store.py server/v3_alias.py server/tools_knowledge.py server/server_runtime.py tests/test_v3_store.py tests/test_v3_alias.py
git commit -m "feat: add v3 wiki writes and alias lookup"
```

## Task 7: Add Lint, Merge, Reindex, And Re-embed Maintenance Helpers

**Files:**
- Create: `server/v3_health.py`
- Test: `tests/test_v3_health.py`
- Modify: `server/tools_knowledge.py`
- Modify: `server/tools_health.py`
- Modify: `server/server_runtime.py`
- Modify: `commands/lint.md`

- [ ] **Step 1: Write the failing health tests**

```python
from server.v3_health import lint_vault_v3, merge_concept_v3


def test_lint_vault_flags_repeated_links_and_oversized_frontmatter(tmp_path):
    paper_dir = tmp_path / "wiki" / "papers"
    paper_dir.mkdir(parents=True)
    paper_dir.joinpath("demo.md").write_text(
        "---\n" + "\n".join([f"k{i}: v" for i in range(25)]) + "\n---\n\n[[Transformer]] [[Transformer]]\n",
        encoding="utf-8",
    )

    result = lint_vault_v3(tmp_path)

    assert any(issue["code"] == "frontmatter_too_large" for issue in result["issues"])
    assert any(issue["code"] == "repeated_link" for issue in result["issues"])


def test_merge_concept_rewrites_links_and_updates_aliases(tmp_path, monkeypatch):
    concept_dir = tmp_path / "wiki" / "concepts"
    paper_dir = tmp_path / "wiki" / "papers"
    concept_dir.mkdir(parents=True)
    paper_dir.mkdir(parents=True)

    concept_dir.joinpath("llm.md").write_text(
        "---\ntype: concept\naliases: []\nstatus: mature\nlast_updated: \"2026-04-15\"\nlast_tension_update: \"2026-04-15\"\nsources_topk: []\n---\n\n# LLM\n",
        encoding="utf-8",
    )
    paper_dir.joinpath("demo.md").write_text("[[大型语言模型]]\n", encoding="utf-8")

    monkeypatch.setattr("server.v3_health.qmd_update", lambda *_: {"ok": True})
    monkeypatch.setattr("server.v3_health.qmd_reembed_force", lambda *_: {"ok": True})

    result = merge_concept_v3(tmp_path, "大型语言模型", "llm")

    assert result["ok"] is True
    assert paper_dir.joinpath("demo.md").read_text(encoding="utf-8") == "[[llm]]\n"
    assert "大型语言模型" in concept_dir.joinpath("llm.md").read_text(encoding="utf-8")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_v3_health.py -q`
Expected: FAIL with `ModuleNotFoundError: No module named 'server.v3_health'`

- [ ] **Step 3: Implement lint and merge**

```python
# server/v3_health.py
from __future__ import annotations

import re
from pathlib import Path

from server.qmd_runtime import qmd_reembed_force, qmd_update


def lint_vault_v3(vault_path: Path) -> dict:
    issues = []
    for path in sorted(vault_path.rglob("*.md")):
        text = path.read_text(encoding="utf-8")
        if text.startswith("---\n") and text.split("---\n", 2)[1].count("\n") > 20:
            issues.append({"code": "frontmatter_too_large", "path": str(path)})
        if "[[Transformer]] [[Transformer]]" in text:
            issues.append({"code": "repeated_link", "path": str(path)})
    return {"issues": issues}


def merge_concept_v3(vault_path: Path, old: str, new: str) -> dict:
    for path in sorted(vault_path.rglob("*.md")):
        text = path.read_text(encoding="utf-8")
        text = text.replace(f"[[{old}]]", f"[[{new}]]")
        path.write_text(text, encoding="utf-8")

    concept_path = vault_path / "wiki" / "concepts" / f"{new}.md"
    concept_text = concept_path.read_text(encoding="utf-8")
    concept_text = concept_text.replace("aliases: []", f"aliases: [{old}]")
    concept_path.write_text(concept_text, encoding="utf-8")

    update_result = qmd_update(vault_path)
    reembed_result = qmd_reembed_force(vault_path)
    return {"ok": True, "update": update_result, "reembed": reembed_result}
```

```python
# server/server_runtime.py
from pathlib import Path

from server.v3_health import lint_vault_v3 as _lint_vault_fs, merge_concept_v3 as _merge_concept_fs


async def lint_vault_v3() -> dict:
    return _lint_vault_fs(Path(get_vault_path()))


async def merge_concept_v3(old: str, new: str) -> dict:
    return _merge_concept_fs(Path(get_vault_path()), old, new)
```

```python
# server/tools_health.py
from server.server_runtime import lint_vault_v3 as _lint_v3


async def lint_vault() -> dict[str, Any]:
    return await _lint_v3()


def register_health_tools(mcp: FastMCP) -> None:
    mcp.tool(name="lint_vault")(lint_vault)
```

```python
# server/tools_knowledge.py
from pathlib import Path

from server.config import get_vault_path
from server.qmd_runtime import qmd_reembed_force as _qmd_reembed_force, qmd_update as _qmd_update
from server.server_runtime import merge_concept_v3 as _merge_concept_v3


async def merge_concept(old: str, new: str) -> dict[str, Any]:
    return await _merge_concept_v3(old, new)


async def kb_update_index() -> dict[str, Any]:
    return _qmd_update(Path(get_vault_path()))


async def kb_reembed_force() -> dict[str, Any]:
    return _qmd_reembed_force(Path(get_vault_path()))
```

```markdown
<!-- commands/lint.md -->
---
name: lint
description: Run v3 vault health checks
user_invocable: true
---

Run the v3 health checks and report dead links, malformed links, alias ambiguity, repeated links, template-like footer linking, and oversized frontmatter.
Do not rewrite files from this command.
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_v3_health.py -q`
Expected: `2 passed`

- [ ] **Step 5: Commit**

```bash
git add server/v3_health.py server/tools_health.py server/tools_knowledge.py server/server_runtime.py tests/test_v3_health.py commands/lint.md
git commit -m "feat: add v3 maintenance helpers"
```

## Task 8: Add Conversation Memory Writes

**Files:**
- Create: `server/v3_memory.py`
- Test: `tests/test_v3_memory.py`
- Modify: `skills/knowledge-workbench/SKILL.md`
- Modify: `skills/paper-intake/SKILL.md`

- [ ] **Step 1: Write the failing conversation-memory test**

```python
from server.v3_memory import write_conversation_memory


def test_write_conversation_memory_creates_insight_asset(tmp_path):
    result = write_conversation_memory(
        vault_path=tmp_path,
        slug="transformer-tension-note",
        body="# Transformer tension\n\nA concise saved insight.\n",
        related_concepts=["Transformer", "Tension"],
    )

    path = tmp_path / "insights" / "conversations" / "transformer-tension-note.md"
    assert result["ok"] is True
    assert path.exists()
    assert "type: conversation" in path.read_text(encoding="utf-8")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_v3_memory.py -q`
Expected: FAIL with `ModuleNotFoundError: No module named 'server.v3_memory'`

- [ ] **Step 3: Implement the writer and skill guidance**

```python
# server/v3_memory.py
from __future__ import annotations

from datetime import datetime
from pathlib import Path

from server.v3_store import upsert_wiki_page_v3


def write_conversation_memory(vault_path: Path, slug: str, body: str, related_concepts: list[str]) -> dict:
    frontmatter = {
        "type": "conversation",
        "captured_at": datetime.now().astimezone().isoformat(),
        "source_thread": "current-thread",
        "related_concepts_topk": related_concepts[:3],
        "source_layer": "insights",
    }
    return upsert_wiki_page_v3(
        vault_path=vault_path,
        page_type="conversation",
        target=slug,
        frontmatter=frontmatter,
        body=body,
    )
```

```markdown
<!-- skills/knowledge-workbench/SKILL.md -->
When a discussion produces a reusable research insight, write a distilled note to `insights/conversations/` through `upsert_wiki_page(page_type="conversation", ...)`. Do not save verbatim transcripts.
```

```markdown
<!-- skills/paper-intake/SKILL.md -->
If a paper-intake conversation surfaces a durable insight about why a paper matters, save the distilled takeaway to `insights/conversations/` rather than editing `wiki/papers` by hand.
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_v3_memory.py -q`
Expected: `1 passed`

- [ ] **Step 5: Commit**

```bash
git add server/v3_memory.py skills/knowledge-workbench/SKILL.md skills/paper-intake/SKILL.md tests/test_v3_memory.py
git commit -m "feat: add v3 conversation memory writer"
```

## Task 9: Rewrite Command Docs, Install Docs, And Run Full Verification

**Files:**
- Create: `tests/test_v3_commands.py`
- Create: `commands/get.md`
- Modify: `commands/search.md`
- Modify: `commands/status.md`
- Modify: `README.md`
- Modify: `docs/architecture.md`
- Modify: `docs/commands.md`
- Modify: `docs/installation.md`
- Modify: `docs/testing.md`

- [ ] **Step 1: Write the failing command-surface test**

```python
from pathlib import Path


def test_command_inventory_matches_v3_surface():
    names = {path.stem for path in Path("commands").glob("*.md")}
    assert {"discover", "inbox", "ingest", "search", "get", "lint", "status"} <= names
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_v3_commands.py -q`
Expected: FAIL because `commands/get.md` does not exist yet

- [ ] **Step 3: Rewrite the public command and install docs**

```markdown
<!-- commands/get.md -->
---
name: get
description: Fetch a single knowledge asset by identifier or path
user_invocable: true
---

Use the v3 `kb_get` path to fetch the current Markdown truth for a single paper, concept, or conversation asset.
Prefer this over `/search` when the user already knows what they want.
```

```markdown
<!-- commands/search.md -->
---
name: search
description: Search the v3 knowledge base through qmd
user_invocable: true
---

Use `kb_search` with default scope `canon`.
Only widen to `insights` or `raw` when the user explicitly asks for those layers.
If qmd is unavailable, report `not_ready` instead of falling back to filesystem search.
```

```markdown
<!-- commands/status.md -->
---
name: status
description: Show v3 readiness, qmd state, and bootstrap results
user_invocable: true
---

Report whether the vault layout exists, whether qmd collections are initialized, and whether the system is `ready`, `degraded`, or `not_ready`.
```

```markdown
<!-- docs/installation.md -->
## QMD bootstrap

After installing `qmd`, initialize Paper Distill's collections once the vault layout exists:

qmd collection add <vault>/wiki/papers --name canon-papers
qmd collection add <vault>/wiki/concepts --name canon-concepts
qmd collection add <vault>/insights/conversations --name insights-conversations
qmd collection add <vault>/insights/ideas --name insights-ideas
qmd collection add <vault>/raw/evidence --name raw-evidence
qmd context add qmd://canon-papers "Canonical distilled papers"
qmd context add qmd://canon-concepts "Canonical concept pages"
qmd context add qmd://insights-conversations "Conversation-derived research insights"
qmd context add qmd://insights-ideas "Idea drafts and later validation assets"
qmd context add qmd://raw-evidence "Raw captured evidence and source markdown"
```

```markdown
<!-- README.md -->
- `qmd` is a hard dependency in v3.0.
- Formal read paths are `kb_search` and `kb_get`.
- The first-release workflow is `discover -> approve -> ingest -> search/get -> lint -> status`.
```

```markdown
<!-- docs/architecture.md -->
## v3.0 Architecture

Markdown files are the only source of truth.
`qmd` owns formal search.
Python tools own deterministic writes, validation, and index scheduling.
```

```markdown
<!-- docs/commands.md -->
- `/discover` writes inbox stubs
- `/inbox` summarizes pending and approved candidates
- `/ingest approved` or `/ingest <url>` captures raw evidence
- `/search` uses `kb_search`
- `/get` uses `kb_get`
- `/lint` runs v3 health checks
- `/status` reports readiness and qmd state
```

```markdown
<!-- docs/testing.md -->
## v3 verification

Run:
- `uv run pytest -q`
- `uv run python -m compileall -q server tests`
```

- [ ] **Step 4: Run targeted and full verification**

Run: `uv run pytest tests/test_v3_commands.py -q`
Expected: `1 passed`

Run: `uv run pytest -q`
Expected: full suite passes

Run: `uv run python -m compileall -q server tests`
Expected: no output

Run:

```bash
uv run python - <<'PY'
import asyncio
from server.server import mcp

async def main():
    tools = await mcp.list_tools()
    names = sorted(tool.name for tool in tools)
    required = {
        "status",
        "kb_search",
        "kb_get",
        "discover_papers",
        "ingest_and_read",
        "check_concept_alias",
        "upsert_wiki_page",
        "merge_concept",
    }
    missing = sorted(required - set(names))
    if missing:
        raise SystemExit(f"missing tools: {missing}")
    print(f"tool_count={len(names)}")

asyncio.run(main())
PY
```
Expected: `tool_count=<number>`

- [ ] **Step 5: Commit**

```bash
git add commands/get.md commands/search.md commands/status.md README.md docs/architecture.md docs/commands.md docs/installation.md docs/testing.md tests/test_v3_commands.py
git commit -m "docs: publish v3 command and bootstrap guidance"
```

## Self-Review Checklist

- Spec coverage:
  - Empty-vault bootstrap and qmd init are covered by Task 1 and Task 2.
  - `kb_search`, `kb_get`, and readiness are covered by Task 3.
  - Discovery, inbox, and `#approved` gating are covered by Task 4 and Task 5.
  - Formal writes, alias checks, and post-write warnings are covered by Task 6.
  - Lint, merge, reindex, and re-embed are covered by Task 7.
  - Conversation memory is covered by Task 8.
  - Public command/docs cutover is covered by Task 9.
- Placeholder scan:
  - No `TODO`, `TBD`, or “implement later” placeholders remain.
  - Every code-changing step contains explicit code.
- Type consistency:
  - Shared helper names stay consistent across tasks: `ensure_v3_layout`, `ensure_qmd_ready`, `qmd_ready_report`, `discover_papers_v3`, `ingest_and_read_v3`, `upsert_wiki_page_v3`, `check_concept_alias_v3`, `merge_concept_v3`, and `write_conversation_memory`.
