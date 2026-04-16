# Paper Distill v3 Purity Cleanup Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Remove all v2 and legacy residue so the repository ships only the current v3 runtime, tests, and documentation.

**Architecture:** First shrink the live MCP surface down to direct v3-only modules, then extract the small shared helpers those modules need, and only then physically delete the old runtime graph. Repository-shape tests become part of the contract so retired files, names, and cache artifacts cannot drift back in.

**Tech Stack:** Python 3.10, FastMCP, qmd CLI, PyYAML, pytest, uv, git

---

## File Map

### Create

- `server/v3_markdown.py` — frontmatter split/render helpers, atomic text writes, and Markdown page writes used only by the v3 modules.
- `server/v3_names.py` — slug and surface-normalization helpers shared by alias, health, and bootstrap code.
- `server/v3_scoring.py` — v3-native search scoring wrapper that stops discovery from calling `server_runtime`.
- `tests/test_repo_purity.py` — exact path and import-shape assertions for the pure-v3 repository.

### Modify

- `server/server.py` — remove the delegate layer and keep only the thin FastMCP entrypoint.
- `server/tools_core.py` — expose only `kb_search`, `kb_get`, and `status`, implemented without `server_runtime`.
- `server/tools_intake.py` — expose only `discover_papers` and `ingest_and_read`.
- `server/tools_knowledge.py` — expose only `check_concept_alias`, `upsert_wiki_page`, `merge_concept`, `kb_update_index`, and `kb_reembed_force`.
- `server/tools_health.py` — expose only `lint_vault`.
- `server/v3_alias.py` — use local v3 name helpers instead of `concept_registry`.
- `server/v3_bootstrap.py` — keep DOI-safe filenames and the full first-release layout.
- `server/v3_discovery.py` — call v3-native search and scoring helpers directly.
- `server/v3_health.py` — use local v3 name and Markdown helpers instead of legacy modules.
- `server/v3_ingest.py` — write raw evidence through `server/v3_markdown.py`.
- `server/v3_store.py` — use shared atomic-write and Markdown helpers.
- `server/paper_scoring.py` — rename `_score_*_v2` helpers to neutral names used by `server/v3_scoring.py`.
- `server/config.py` — remove stale `Paper Distill v2` defaults and trim config keys that no live v3 path uses.
- `tests/test_server_architecture.py` — assert the entrypoint no longer imports `server_runtime` or compatibility bindings.
- `tests/test_v3_alias.py`
- `tests/test_v3_commands.py`
- `tests/test_v3_discovery.py`
- `tests/test_v3_health.py`
- `tests/test_v3_ingest.py`
- `tests/test_v3_store.py`
- `tests/test_no_retired_names.py`
- `README.md`
- `docs/README.md`
- `docs/architecture.md`
- `docs/commands.md`
- `docs/configuration.md`
- `docs/frontmatter-reference.md`
- `docs/installation.md`
- `docs/testing.md`
- `docs/vault-layout.md`

### Delete

- Runtime modules:
  `server/active_threads.py`,
  `server/capture_settings.py`,
  `server/compile_ir.py`,
  `server/concept_registry.py`,
  `server/context_assembler.py`,
  `server/crgp_tools.py`,
  `server/database.py`,
  `server/dialogue_capture.py`,
  `server/discovery_helpers.py`,
  `server/idea_verification.py`,
  `server/ingestion_helpers.py`,
  `server/maintenance.py`,
  `server/memory_compile.py`,
  `server/memory_consolidation.py`,
  `server/memory_contract.py`,
  `server/memory_promotion.py`,
  `server/memory_runtime.py`,
  `server/obsidian_query.py`,
  `server/paper_frontmatter.py`,
  `server/paper_identity.py`,
  `server/research_item.py`,
  `server/server_runtime.py`,
  `server/template_render.py`,
  `server/tools_ideas.py`,
  `server/vault_contract.py`,
  `server/vault_lint.py`,
  `server/vault_ops.py`,
  `server/vault_query.py`,
  `server/zotero/__init__.py`,
  `server/zotero/client.py`
- Tests:
  `tests/test_asset_writers.py`,
  `tests/test_compile_ir.py`,
  `tests/test_compile_patch_engine.py`,
  `tests/test_context_assembler.py`,
  `tests/test_crgp_unified.py`,
  `tests/test_database_schema.py`,
  `tests/test_dialogue_capture.py`,
  `tests/test_idea_verification.py`,
  `tests/test_maintenance_execution.py`,
  `tests/test_memory_compile.py`,
  `tests/test_memory_contract.py`,
  `tests/test_memory_promotion.py`,
  `tests/test_memory_runtime.py`,
  `tests/test_obsidian_query.py`,
  `tests/test_paper_add.py`,
  `tests/test_productization.py`,
  `tests/test_registry_maintenance.py`,
  `tests/test_server_tools.py`,
  `tests/test_template_inventory.py`,
  `tests/test_trigger_candidates.py`,
  `tests/test_vault_lint.py`,
  `tests/test_vault_query.py`,
  `tests/test_writer_boundaries.py`,
  `tests/test_zotero_client.py`
- Docs:
  `docs/compile-ir-schema.md`,
  `docs/mcp-tool-reference.md`,
  `docs/obsidian-cli-validation.md`,
  `docs/skill-agent-boundary.md`,
  `docs/troubleshooting.md`,
  `docs/workflows.md`,
  `docs/superpowers/specs/2026-04-15-paper-distill-v3-design.md`,
  `docs/superpowers/plans/2026-04-15-paper-distill-v3-implementation.md`
- Tracked cache directories:
  `server/__pycache__/`,
  `server/search/__pycache__/`,
  `server/zotero/__pycache__/`,
  `tests/__pycache__/`

## Task 1: Remove The Delegate Layer From The Live MCP Surface

**Files:**
- Modify: `server/server.py`
- Modify: `server/tools_core.py`
- Modify: `server/tools_intake.py`
- Modify: `server/tools_knowledge.py`
- Modify: `server/tools_health.py`
- Modify: `tests/test_server_architecture.py`
- Modify: `tests/test_v3_store.py`

- [ ] **Step 1: Write the failing architecture tests**

```python
# tests/test_server_architecture.py
from __future__ import annotations

import ast
from pathlib import Path


def test_server_entrypoint_is_thin_and_v3_only() -> None:
    path = Path(__file__).resolve().parents[1] / "server/server.py"
    source = path.read_text(encoding="utf-8")
    tree = ast.parse(source)

    top_level_defs = [
        node
        for node in tree.body
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
    ]

    assert "server_runtime" not in source
    assert "_DELEGATED_ASYNC_NAMES" not in source
    assert "_delegate_async" not in source
    assert "compatibility bindings" not in source
    assert "register_core_tools(mcp)" in source
    assert "register_intake_tools(mcp)" in source
    assert "register_knowledge_tools(mcp)" in source
    assert "register_health_tools(mcp)" in source
    assert len(top_level_defs) <= 1


def test_server_entrypoint_has_no_runtime_delegate_exports() -> None:
    source = (Path(__file__).resolve().parents[1] / "server/server.py").read_text(encoding="utf-8")

    assert "upsert_wiki_page_v3" not in source
    assert "check_concept_alias_v3" not in source
```

- [ ] **Step 2: Run the targeted tests to verify they fail**

Run: `uv run pytest tests/test_server_architecture.py tests/test_v3_store.py -q`
Expected: FAIL because `server/server.py` still imports `server_runtime` and `tests/test_v3_store.py` still expects delegate exports.

- [ ] **Step 3: Rewrite the entrypoint and tool facades to call the v3 modules directly**

```python
# server/server.py
"""Thin Paper Distill v3 MCP entrypoint."""
from __future__ import annotations

from fastmcp import FastMCP

from server.tools_core import register_core_tools
from server.tools_health import register_health_tools
from server.tools_intake import register_intake_tools
from server.tools_knowledge import register_knowledge_tools

mcp = FastMCP("paper-distill")

register_core_tools(mcp)
register_intake_tools(mcp)
register_knowledge_tools(mcp)
register_health_tools(mcp)


def main() -> None:
    mcp.run()
```

```python
# server/tools_core.py
from __future__ import annotations

from pathlib import Path
from typing import Any

from fastmcp import FastMCP

from server.config import get_vault_path
from server.qmd_runtime import qmd_get, qmd_ready_report, qmd_search
from server.v3_bootstrap import ensure_v3_layout


def _vault_path() -> Path:
    raw = str(get_vault_path()).strip()
    if not raw:
        raise ValueError("VAULT_PATH not configured.")
    path = Path(raw)
    ensure_v3_layout(path)
    return path


async def kb_search(query: str, scope: str = "canon") -> dict[str, Any]:
    return qmd_search(vault_path=_vault_path(), query=query, scope=scope)


async def kb_get(id_or_path: str) -> dict[str, Any]:
    return qmd_get(vault_path=_vault_path(), id_or_path=id_or_path)


async def status() -> dict[str, Any]:
    path = _vault_path()
    return {
        "ok": True,
        "layout": ensure_v3_layout(path),
        "qmd": qmd_ready_report(path),
    }


def register_core_tools(mcp: FastMCP) -> None:
    mcp.tool(name="kb_search")(kb_search)
    mcp.tool(name="kb_get")(kb_get)
    mcp.tool(name="status")(status)
```

```python
# server/tools_intake.py
from __future__ import annotations

from typing import Any

from fastmcp import FastMCP

from server.v3_discovery import discover_papers_v3
from server.v3_ingest import ingest_and_read_v3


async def discover_papers(query: str | None = None) -> dict[str, Any]:
    return await discover_papers_v3(query=query)


async def ingest_and_read(input_value: str) -> dict[str, Any]:
    return await ingest_and_read_v3(input_value=input_value)


def register_intake_tools(mcp: FastMCP) -> None:
    mcp.tool(name="discover_papers")(discover_papers)
    mcp.tool(name="ingest_and_read")(ingest_and_read)
```

```python
# server/tools_health.py
from __future__ import annotations

from pathlib import Path
from typing import Any

from fastmcp import FastMCP

from server.config import get_vault_path
from server.v3_health import lint_vault_v3


async def lint_vault() -> dict[str, Any]:
    vault_path = Path(str(get_vault_path()).strip())
    return lint_vault_v3(vault_path)


def register_health_tools(mcp: FastMCP) -> None:
    mcp.tool(name="lint_vault")(lint_vault)
```

```python
# server/tools_knowledge.py
from __future__ import annotations

from pathlib import Path
from typing import Any

from fastmcp import FastMCP

from server.config import get_vault_path
from server.qmd_runtime import qmd_reembed_force, qmd_update
from server.v3_alias import check_concept_alias_v3
from server.v3_bootstrap import ensure_v3_layout
from server.v3_health import merge_concept_v3
from server.v3_store import upsert_wiki_page_v3


def _vault_path() -> Path:
    raw = str(get_vault_path()).strip()
    if not raw:
        raise ValueError("VAULT_PATH not configured.")
    path = Path(raw)
    ensure_v3_layout(path)
    return path


async def upsert_wiki_page(page_type: str, target: str, frontmatter: dict, body: str) -> dict[str, Any]:
    return upsert_wiki_page_v3(vault_path=_vault_path(), page_type=page_type, target=target, frontmatter=frontmatter, body=body)


async def check_concept_alias(name: str) -> dict[str, Any]:
    return check_concept_alias_v3(_vault_path(), name)


async def merge_concept(old: str, new: str) -> dict[str, Any]:
    return merge_concept_v3(_vault_path(), old=old, new=new)


async def kb_update_index() -> dict[str, Any]:
    return qmd_update(_vault_path())


async def kb_reembed_force() -> dict[str, Any]:
    return qmd_reembed_force(_vault_path())


def register_knowledge_tools(mcp: FastMCP) -> None:
    mcp.tool(name="upsert_wiki_page")(upsert_wiki_page)
    mcp.tool(name="check_concept_alias")(check_concept_alias)
    mcp.tool(name="merge_concept")(merge_concept)
    mcp.tool(name="kb_update_index")(kb_update_index)
    mcp.tool(name="kb_reembed_force")(kb_reembed_force)
```

- [ ] **Step 4: Update the store-facing test to reflect the new direct registration shape and rerun**

```python
# tests/test_v3_store.py
from __future__ import annotations

from pathlib import Path


def test_server_entrypoint_registers_tools_without_delegate_layer() -> None:
    source = (Path(__file__).resolve().parents[1] / "server/server.py").read_text(encoding="utf-8")

    assert "server_runtime" not in source
    assert "_DELEGATED_ASYNC_NAMES" not in source
    assert "register_knowledge_tools(mcp)" in source
```

Run: `uv run pytest tests/test_server_architecture.py tests/test_v3_store.py tests/test_v3_commands.py -q`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add server/server.py server/tools_core.py server/tools_intake.py server/tools_health.py \
  server/tools_knowledge.py tests/test_server_architecture.py tests/test_v3_store.py tests/test_v3_commands.py
git commit -m "refactor: remove runtime delegate layer from v3 surface"
```

## Task 2: Extract Shared V3 Helpers And Detach Live Modules From Legacy Imports

**Files:**
- Create: `server/v3_markdown.py`
- Create: `server/v3_names.py`
- Create: `server/v3_scoring.py`
- Create: `tests/test_repo_purity.py`
- Modify: `server/v3_alias.py`
- Modify: `server/v3_discovery.py`
- Modify: `server/v3_health.py`
- Modify: `server/v3_ingest.py`
- Modify: `server/v3_store.py`
- Modify: `server/paper_scoring.py`
- Modify: `server/tools_knowledge.py`
- Modify: `tests/test_v3_alias.py`
- Modify: `tests/test_v3_discovery.py`
- Modify: `tests/test_v3_health.py`
- Modify: `tests/test_v3_ingest.py`
- Modify: `tests/test_v3_store.py`

- [ ] **Step 1: Write the failing purity and behavior tests**

```python
# tests/test_repo_purity.py
from __future__ import annotations

from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
LIVE_V3_MODULES = [
    "server/v3_alias.py",
    "server/v3_discovery.py",
    "server/v3_health.py",
    "server/v3_ingest.py",
    "server/v3_store.py",
    "server/tools_core.py",
    "server/tools_intake.py",
    "server/tools_knowledge.py",
    "server/tools_health.py",
]
FORBIDDEN_IMPORTS = [
    "server_runtime",
    "concept_registry",
    "vault_ops",
    "vault_query",
    "vault_lint",
]


def test_live_v3_modules_do_not_import_legacy_runtime() -> None:
    offenders: list[str] = []
    for rel in LIVE_V3_MODULES:
        source = (REPO_ROOT / rel).read_text(encoding="utf-8")
        for forbidden in FORBIDDEN_IMPORTS:
            if forbidden in source:
                offenders.append(f"{rel}: {forbidden}")
    assert offenders == []
```

```python
# tests/test_v3_discovery.py
def test_discover_papers_uses_v3_scoring_module(tmp_path, monkeypatch) -> None:
    async def fake_search(*args, **kwargs):
        return [{"title": "Demo", "paper_id": "arxiv:2501.00001", "source_url": "https://arxiv.org/abs/2501.00001"}]

    score_calls = []

    async def fake_score(*args, **kwargs):
        score_calls.append("v3")
        return [{"title": "Demo", "paper_id": "arxiv:2501.00001", "source_url": "https://arxiv.org/abs/2501.00001", "_score": 91}]

    monkeypatch.setattr("server.v3_discovery.search_papers_v3", fake_search)
    monkeypatch.setattr("server.v3_discovery.score_papers_v3", fake_score)
    monkeypatch.setattr("server.v3_discovery.get_vault_path", lambda: str(tmp_path))

    asyncio.run(discover_papers_v3(query="demo"))

    assert score_calls == ["v3"]
```

- [ ] **Step 2: Run the focused tests to verify they fail**

Run: `uv run pytest tests/test_repo_purity.py tests/test_v3_discovery.py tests/test_v3_ingest.py tests/test_v3_health.py tests/test_v3_store.py -q`
Expected: FAIL because the live modules still import `server_runtime`, `concept_registry`, and `vault_ops`.

- [ ] **Step 3: Add the shared helpers and rewire the live v3 modules**

```python
# server/v3_names.py
from __future__ import annotations

import re

_NON_ALPHANUM = re.compile(r"[^a-z0-9]+")
_NON_WORD_RE = re.compile(r"[\W_]+", re.UNICODE)


def slugify(text: str) -> str:
    return _NON_ALPHANUM.sub("-", text.lower().strip()).strip("-")


def surface_key(value: str) -> str:
    normalized = value.casefold().strip()
    if normalized.isascii():
        return slugify(normalized)
    return _NON_WORD_RE.sub("", normalized)
```

```python
# server/v3_markdown.py
from __future__ import annotations

import os
import tempfile
from io import StringIO
from pathlib import Path
from typing import Any

import yaml


def split_frontmatter(text: str) -> tuple[dict[str, Any], str, bool]:
    if not text.startswith("---\n"):
        return {}, text, False
    _, remainder = text.split("---\n", 1)
    fm_text, body = remainder.split("\n---\n", 1)
    payload = yaml.safe_load(fm_text) or {}
    return payload if isinstance(payload, dict) else {}, body, True


def render_markdown(frontmatter: dict[str, Any], body: str) -> str:
    stream = StringIO()
    stream.write("---\n")
    stream.write(yaml.safe_dump(frontmatter, sort_keys=False, allow_unicode=True, default_flow_style=False).strip())
    stream.write("\n---\n\n")
    stream.write(body.rstrip())
    stream.write("\n")
    return stream.getvalue()


def atomic_write_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=path.parent, prefix=f".{path.stem}.", suffix=".tmp", delete=False) as handle:
            tmp_path = Path(handle.name)
            handle.write(content)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(tmp_path, path)
        tmp_path = None
    finally:
        if tmp_path is not None and tmp_path.exists():
            tmp_path.unlink()
```

```python
# server/v3_scoring.py
from __future__ import annotations

import asyncio
from typing import Any

from server.config import get_paper_distill_settings, get_scoring_settings, get_topics
from server.paper_scoring import (
    _annotate_paper,
    _best_topic_fit,
    _score_author_preference,
    _score_impact,
    _score_metadata_quality,
    _score_novelty,
    _score_recency,
    _score_venue_tier,
)
from server.search import dedup_merge, search_arxiv, search_dblp, search_openalex, search_papers_with_code, search_semantic_scholar

_SEARCH_SOURCES = {
    "arxiv": search_arxiv,
    "s2": search_semantic_scholar,
    "openalex": search_openalex,
    "dblp": search_dblp,
    "pwc": search_papers_with_code,
}


async def search_papers_v3(query: str, sources: list[str] | None = None, max_results: int = 20) -> list[dict[str, Any]]:
    names = sources or list(_SEARCH_SOURCES)
    tasks = [asyncio.wait_for(_SEARCH_SOURCES[name](query, max_results=max_results), 15) for name in names]
    results = await asyncio.gather(*tasks, return_exceptions=True)
    batches = [batch for batch in results if isinstance(batch, list)]
    return dedup_merge(batches)


async def score_papers_v3(papers: list[dict[str, Any]]) -> list[dict[str, Any]]:
    scoring = get_scoring_settings()
    topics = get_topics()
    profile = get_paper_distill_settings().get("research_profile", {})
    learned = profile.get("learned_preferences", {}) if isinstance(profile, dict) else {}
    weights = scoring.get("weights", {})
    venue_aliases = scoring.get("venue_aliases", {})
    venue_tiers = scoring.get("venue_tiers", {})
    whitelist_authors = profile.get("whitelist_authors", []) if isinstance(profile, dict) else []
    preferred_venues = learned.get("preferred_venues", []) if isinstance(learned, dict) else []

    known_ids: set[str] = set()
    scored: list[dict[str, Any]] = []
    for paper in papers:
        annotated = _annotate_paper(paper, venue_aliases=venue_aliases, venue_tiers=venue_tiers)
        _best_topic, topic_fit = _best_topic_fit(annotated, topics)
        total = (
            weights.get("topic_fit", 0.40) * topic_fit
            + weights.get("recency", 0.20) * _score_recency(annotated)
            + weights.get("novelty", 0.15) * _score_novelty(annotated, known_ids)
            + weights.get("impact", 0.10) * _score_impact(annotated)
            + weights.get("venue_tier", 0.07) * _score_venue_tier(annotated)
            + weights.get("author_preference", 0.05) * _score_author_preference(annotated, whitelist_authors, preferred_venues)
            + weights.get("metadata_quality", 0.03) * _score_metadata_quality(annotated)
        )
        annotated["_score"] = int(round(total * 100))
        known_ids.add(str(annotated.get("paper_id", "")))
        scored.append(annotated)
    return sorted(scored, key=lambda item: (-int(item.get("_score", 0)), str(item.get("paper_id", ""))))
```

```python
# server/v3_discovery.py
from server.v3_scoring import score_papers_v3, search_papers_v3

async def discover_papers_v3(query: str | None = None) -> dict[str, Any]:
    vault_path_value = str(get_vault_path()).strip()
    if not vault_path_value:
        return {"error": "VAULT_PATH not configured. Set it in settings.json or env."}

    vault_path = Path(vault_path_value)
    ensure_v3_layout(vault_path)
    cache = _load_seen_cache(vault_path)
    results = await search_papers_v3(query=query or "", sources=None, max_results=20)
    scored_results = await score_papers_v3(results)
    saved: list[dict[str, Any]] = []
    skipped_seen: list[str] = []
    discovered_on = date.today().isoformat()
    for paper in scored_results:
        pid = str(paper.get("paper_id", "")).strip()
        title = str(paper.get("title", "")).strip()
        if not pid or not title or pid in cache:
            continue
        score = _paper_score(paper)
        inbox_path = vault_path / "inbox" / paper_filename(title, pid)
        inbox_path.write_text(_render_inbox_stub(paper, score), encoding="utf-8")
        cache[pid] = {"title": title, "score": score, "added_at": discovered_on}
        saved.append({"paper_id": pid, "path": str(inbox_path), "score": score})
    _write_seen_cache(vault_path, cache)
    return {"saved": saved, "skipped_seen": skipped_seen}
```

```python
# server/v3_ingest.py
from server.v3_markdown import render_markdown

def _write_raw_evidence(vault_path: Path, capture: dict[str, Any]) -> Path:
    paper_id_value = str(capture["paper_id"])
    raw_path = _existing_raw_evidence_path(vault_path, paper_id_value)
    if raw_path is None:
        raw_path = vault_path / "raw" / "evidence" / paper_filename(str(capture["title"]), paper_id_value)
    frontmatter = {
        "type": "raw_evidence",
        "paper_id": paper_id_value,
        "title": capture["title"],
        "source_url": capture["source_url"],
        "captured_at": capture["captured_at"],
        "content_hash": capture["content_hash"],
    }
    raw_path.write_text(render_markdown(frontmatter, str(capture["markdown"])), encoding="utf-8")
    return raw_path
```

```python
# server/v3_alias.py and server/v3_health.py
from server.v3_markdown import render_markdown, split_frontmatter
from server.v3_names import slugify, surface_key

# in v3_alias.py
def _normalize(value: str) -> str:
    normalized = value.casefold().strip()
    return slugify(normalized) if normalized.isascii() else surface_key(normalized)


# in v3_health.py
def _surface_key(value: str) -> str:
    normalized = value.casefold().strip()
    return slugify(normalized) if normalized.isascii() else surface_key(normalized)
```

- [ ] **Step 4: Rename the scoring helpers and rerun the focused tests**

```bash
perl -0pi -e 's/_score_recency_v2/_score_recency/g; s/_score_impact_v2/_score_impact/g; s/_score_novelty_v2/_score_novelty/g; s/_score_venue_tier_v2/_score_venue_tier/g; s/_score_author_preference_v2/_score_author_preference/g; s/_score_metadata_quality_v2/_score_metadata_quality/g' \
  server/paper_scoring.py server/v3_scoring.py

rg -n "_score_.*_v2|Paper Distill v2" server/paper_scoring.py server/v3_scoring.py server/config.py
```

Run: `uv run pytest tests/test_repo_purity.py tests/test_v3_alias.py tests/test_v3_discovery.py tests/test_v3_health.py tests/test_v3_ingest.py tests/test_v3_store.py -q`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add server/v3_markdown.py server/v3_names.py server/v3_scoring.py server/v3_alias.py \
  server/v3_discovery.py server/v3_health.py server/v3_ingest.py server/v3_store.py \
  server/paper_scoring.py server/tools_knowledge.py tests/test_repo_purity.py tests/test_v3_alias.py \
  tests/test_v3_discovery.py tests/test_v3_health.py tests/test_v3_ingest.py tests/test_v3_store.py
git commit -m "refactor: detach live v3 modules from legacy helpers"
```

## Task 3: Delete Legacy Runtime Files, Tests, And Tracked Cache Artifacts

**Files:**
- Delete: `server/active_threads.py`
- Delete: `server/capture_settings.py`
- Delete: `server/compile_ir.py`
- Delete: `server/concept_registry.py`
- Delete: `server/context_assembler.py`
- Delete: `server/crgp_tools.py`
- Delete: `server/database.py`
- Delete: `server/dialogue_capture.py`
- Delete: `server/discovery_helpers.py`
- Delete: `server/idea_verification.py`
- Delete: `server/ingestion_helpers.py`
- Delete: `server/maintenance.py`
- Delete: `server/memory_compile.py`
- Delete: `server/memory_consolidation.py`
- Delete: `server/memory_contract.py`
- Delete: `server/memory_promotion.py`
- Delete: `server/memory_runtime.py`
- Delete: `server/obsidian_query.py`
- Delete: `server/paper_frontmatter.py`
- Delete: `server/paper_identity.py`
- Delete: `server/research_item.py`
- Delete: `server/server_runtime.py`
- Delete: `server/template_render.py`
- Delete: `server/tools_ideas.py`
- Delete: `server/vault_contract.py`
- Delete: `server/vault_lint.py`
- Delete: `server/vault_ops.py`
- Delete: `server/vault_query.py`
- Delete: `server/zotero/__init__.py`
- Delete: `server/zotero/client.py`
- Delete: the legacy test files listed in the File Map
- Delete: `server/__pycache__/`
- Delete: `server/search/__pycache__/`
- Delete: `server/zotero/__pycache__/`
- Delete: `tests/__pycache__/`
- Modify: `tests/test_repo_purity.py`
- Modify: `tests/test_no_retired_names.py`

- [ ] **Step 1: Extend the repository-shape tests with exact path assertions**

```python
# tests/test_repo_purity.py
LEGACY_PATHS = [
    "server/server_runtime.py",
    "server/compile_ir.py",
    "server/database.py",
    "server/obsidian_query.py",
    "server/vault_query.py",
    "server/vault_lint.py",
    "server/vault_ops.py",
    "server/concept_registry.py",
    "server/maintenance.py",
    "server/zotero/client.py",
    "tests/test_server_tools.py",
    "tests/test_paper_add.py",
    "tests/test_registry_maintenance.py",
    "docs/mcp-tool-reference.md",
    "docs/compile-ir-schema.md",
]


def test_legacy_paths_are_removed() -> None:
    offenders = [rel for rel in LEGACY_PATHS if (REPO_ROOT / rel).exists()]
    assert offenders == []


def test_repository_contains_no_checked_in_pycache_dirs() -> None:
    offenders = [
        str(path.relative_to(REPO_ROOT))
        for path in REPO_ROOT.rglob("__pycache__")
        if ".venv" not in path.parts and ".worktrees" not in path.parts
    ]
    assert offenders == []
```

- [ ] **Step 2: Run the purity tests to verify they fail**

Run: `uv run pytest tests/test_repo_purity.py tests/test_no_retired_names.py -q`
Expected: FAIL because the listed legacy files and tracked `__pycache__` directories still exist.

- [ ] **Step 3: Physically delete the retired runtime graph, legacy tests, and tracked caches**

```bash
git rm server/active_threads.py server/capture_settings.py server/compile_ir.py \
  server/concept_registry.py server/context_assembler.py server/crgp_tools.py \
  server/database.py server/dialogue_capture.py server/discovery_helpers.py \
  server/idea_verification.py server/ingestion_helpers.py server/maintenance.py \
  server/memory_compile.py server/memory_consolidation.py server/memory_contract.py \
  server/memory_promotion.py server/memory_runtime.py server/obsidian_query.py \
  server/paper_frontmatter.py server/paper_identity.py server/research_item.py \
  server/server_runtime.py server/template_render.py server/tools_ideas.py \
  server/vault_contract.py server/vault_lint.py server/vault_ops.py server/vault_query.py \
  server/zotero/__init__.py server/zotero/client.py

git rm tests/test_asset_writers.py tests/test_compile_ir.py tests/test_compile_patch_engine.py \
  tests/test_context_assembler.py tests/test_crgp_unified.py tests/test_database_schema.py \
  tests/test_dialogue_capture.py tests/test_idea_verification.py tests/test_maintenance_execution.py \
  tests/test_memory_compile.py tests/test_memory_contract.py tests/test_memory_promotion.py \
  tests/test_memory_runtime.py tests/test_obsidian_query.py tests/test_paper_add.py \
  tests/test_productization.py tests/test_registry_maintenance.py tests/test_server_tools.py \
  tests/test_template_inventory.py tests/test_trigger_candidates.py tests/test_vault_lint.py \
  tests/test_vault_query.py tests/test_writer_boundaries.py tests/test_zotero_client.py

rm -rf server/__pycache__ server/search/__pycache__ server/zotero/__pycache__ tests/__pycache__
```

- [ ] **Step 4: Tighten the banned-name scan and rerun the purity tests**

```python
# tests/test_no_retired_names.py
banned = [
    "query-library",
    "source-discover",
    "source-ingest",
    "paper-distill-extract",
    "knowledge-compile-resolve",
    "knowledge-compile-publish",
    "knowledge-compile-status",
    "vault-health",
    "update_learned_preferences",
    "Paper Distill v2",
]
```

Run: `uv run pytest tests/test_repo_purity.py tests/test_no_retired_names.py -q`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add tests/test_repo_purity.py tests/test_no_retired_names.py
git commit -m "refactor: delete legacy runtime graph and test residue"
```

## Task 4: Rewrite The Surviving Docs As Pure V3 Documentation

**Files:**
- Modify: `README.md`
- Modify: `docs/README.md`
- Modify: `docs/architecture.md`
- Modify: `docs/commands.md`
- Modify: `docs/configuration.md`
- Modify: `docs/frontmatter-reference.md`
- Modify: `docs/installation.md`
- Modify: `docs/testing.md`
- Modify: `docs/vault-layout.md`
- Delete: `docs/compile-ir-schema.md`
- Delete: `docs/mcp-tool-reference.md`
- Delete: `docs/obsidian-cli-validation.md`
- Delete: `docs/skill-agent-boundary.md`
- Delete: `docs/troubleshooting.md`
- Delete: `docs/workflows.md`
- Delete: `docs/superpowers/specs/2026-04-15-paper-distill-v3-design.md`
- Delete: `docs/superpowers/plans/2026-04-15-paper-distill-v3-implementation.md`
- Modify: `tests/test_v3_commands.py`

- [ ] **Step 1: Write the failing doc-shape assertions**

```python
# tests/test_v3_commands.py
def test_doc_inventory_matches_pure_v3_set() -> None:
    docs_dir = REPO_ROOT / "docs"
    names = {path.name for path in docs_dir.glob("*.md")}
    assert names == {
        "README.md",
        "architecture.md",
        "commands.md",
        "configuration.md",
        "frontmatter-reference.md",
        "installation.md",
        "testing.md",
        "vault-layout.md",
    }


def test_pure_v3_docs_drop_retired_public_names() -> None:
    configuration = (REPO_ROOT / "docs/configuration.md").read_text(encoding="utf-8")
    frontmatter = (REPO_ROOT / "docs/frontmatter-reference.md").read_text(encoding="utf-8")

    assert "query-library" not in configuration
    assert "obsidian_query" not in configuration
    assert "source-discover" not in frontmatter
    assert "knowledge-compile-publish" not in frontmatter
```

- [ ] **Step 2: Run the doc tests to verify they fail**

Run: `uv run pytest tests/test_v3_commands.py -q`
Expected: FAIL because the old docs still exist and `configuration.md` / `frontmatter-reference.md` still reference retired surfaces.

- [ ] **Step 3: Rewrite the kept docs and delete the retired ones**

```text
# docs/configuration.md
# Configuration

Configuration lives in `settings.json` by default. Point to another file with `SETTINGS_PATH`.

## Minimal Configuration

{
  "paper_distill": {
    "vault_path": "/absolute/path/to/your/vault",
    "topics": {
      "manipulation": {
        "label": "Robot Manipulation",
        "keywords": ["manipulation", "robot learning"]
      }
    }
  }
}

## Runtime Keys Used By v3

- `vault_path`
- `topics`
- `search.sources`
- `search.max_per_topic`
- `search.max_daily`
- `workflow.max_candidates_per_topic`
- `workflow.diversity_cap_per_cluster`
- `workflow.require_arxiv_binding`
- `capture.*`
- `venue.authority_order`
- `scoring.*`
- `research_profile.direction`
- `research_profile.whitelist_authors`
- `research_profile.seed_papers`
```

```text
# docs/frontmatter-reference.md
# Frontmatter Reference

## inbox stubs

- `type: inbox_stub`
- `paper_id`
- `title`
- `source_url`
- `discovered_at`
- `score`

## raw evidence

- `type: raw_evidence`
- `paper_id`
- `title`
- `source_url`
- `captured_at`
- `content_hash`

## wiki papers

- `type: paper`
- `paper_id`
- `year`
- `status`
- `key_concepts_topk`
- `source_layer`

## wiki concepts

- `type: concept`
- `concept`
- `aliases`
- `status`
- `sources_topk`

## saved conversations

- `type: conversation`
- `related_concepts_topk`
- `created_at`
```

```bash
git rm docs/compile-ir-schema.md docs/mcp-tool-reference.md docs/obsidian-cli-validation.md \
  docs/skill-agent-boundary.md docs/troubleshooting.md docs/workflows.md \
  docs/superpowers/specs/2026-04-15-paper-distill-v3-design.md \
  docs/superpowers/plans/2026-04-15-paper-distill-v3-implementation.md
```

- [ ] **Step 4: Rerun the doc tests and the command-surface tests**

Run: `uv run pytest tests/test_v3_commands.py tests/test_no_retired_names.py -q`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add README.md docs/README.md docs/architecture.md docs/commands.md docs/configuration.md \
  docs/frontmatter-reference.md docs/installation.md docs/testing.md docs/vault-layout.md \
  tests/test_v3_commands.py
git commit -m "docs: rewrite repository docs as pure v3"
```

## Task 5: Run Full Verification And Finish The Cleanup Branch

**Files:**
- Modify: any touched file only if verification exposes a real regression

- [ ] **Step 1: Run the focused v3 test modules**

Run: `uv run pytest tests/test_v3_bootstrap.py tests/test_qmd_runtime.py tests/test_v3_commands.py tests/test_v3_alias.py tests/test_v3_discovery.py tests/test_v3_health.py tests/test_v3_ingest.py tests/test_v3_store.py tests/test_repo_purity.py tests/test_no_retired_names.py -q`
Expected: PASS

- [ ] **Step 2: Run the full test suite**

Run: `uv run pytest -q`
Expected: PASS with only the retained v3-oriented suite present.

- [ ] **Step 3: Run compile and MCP smoke verification**

Run: `uv run python -m compileall -q server tests`
Expected: PASS with no output

Run:

```bash
uv run python - <<'PY'
import asyncio
from server.server import mcp

async def main():
    tools = await mcp.list_tools()
    names = sorted(tool.name for tool in tools)
    expected = {
        "check_concept_alias",
        "discover_papers",
        "ingest_and_read",
        "kb_get",
        "kb_reembed_force",
        "kb_search",
        "kb_update_index",
        "lint_vault",
        "merge_concept",
        "status",
        "upsert_wiki_page",
    }
    assert set(names) == expected, names
    print(f"tool_count={len(names)}")

asyncio.run(main())
PY
```

Expected: `tool_count=11`

- [ ] **Step 4: Run one final residue scan**

Run:

```bash
rg -n "query-library|source-discover|source-ingest|paper-distill-extract|knowledge-compile-|vault-health|update_learned_preferences|Paper Distill v2" \
  server tests docs commands README.md
```

Expected: no matches

- [ ] **Step 5: Commit**

```bash
git add -A
git commit -m "refactor: purge v2 residue from paper distill v3"
```
