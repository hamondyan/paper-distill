# QMD CLI Boundary Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the five QMD-wrapper MCP tools with direct QMD CLI usage, keep only six Paper Distill business MCP tools, and teach agents to use `qmd` CLI through `docs/qmd-cli.md`, skills, and retained business command docs.

**Architecture:** QMD becomes the only read and index-maintenance interface. Paper Distill MCP shrinks to business operations only. `paper-distill-admin bootstrap` remains as the one-time vault and QMD initialization entry, while write tools stop invoking QMD commands and instead return follow-up guidance for a later `qmd update` / `qmd embed -f` round.

**Tech Stack:** Python 3.10, FastMCP, QMD CLI, pytest, Markdown docs, shell bootstrap script

---

## File Map

### Create

- `docs/qmd-cli.md` — canonical repository guide for QMD CLI usage in Paper Distill

### Delete

- `server/tools_core.py` — removed QMD-wrapper MCP registration layer
- `commands/get.md` — read path now taught through QMD CLI
- `commands/search.md` — read path now taught through QMD CLI
- `commands/status.md` — index health now taught through QMD CLI

### Modify

- `server/server.py` — register only intake, knowledge, and health business tools
- `server/cli.py` — keep bootstrap only, but ensure output is bootstrap-centric rather than runtime-status-centric
- `server/qmd_runtime.py` — trim to bootstrap-only collection/context initialization helpers
- `server/tools_knowledge.py` — keep only business knowledge tools
- `server/v3_store.py` — remove `qmd update` side effects and return follow-up instructions
- `server/v3_health.py` — remove `qmd update` / `qmd embed -f` side effects from concept merge and return follow-up instructions
- `README.md` — point read/index operations to QMD CLI and `docs/qmd-cli.md`
- `docs/README.md` — add `qmd-cli.md` as core documentation
- `docs/architecture.md` — document QMD CLI as the only read/index path
- `docs/commands.md` — restrict command docs to business commands only
- `docs/installation.md` — point post-bootstrap usage to `docs/qmd-cli.md`
- `docs/testing.md` — replace wrapper-tool smoke assumptions with CLI-native checks
- `commands/discover.md` — keep only discovery business guidance
- `commands/inbox.md` — keep inbox approval guidance
- `commands/ingest.md` — keep ingest guidance and post-write QMD follow-up
- `commands/lint.md` — keep Paper Distill lint guidance
- `skills/paper-intake/SKILL.md` — teach business MCP plus QMD CLI read path
- `skills/knowledge-workbench/SKILL.md` — teach QMD CLI for read/index maintenance and business MCP for writes
- `skills/idea-workbench/SKILL.md` — teach QMD CLI for evidence reads and business MCP for writes
- `skills/*/agents/openai.yaml` — refresh short descriptions and prompts where they mention old read wrappers
- `hooks/session-start` — optional light reference to `docs/qmd-cli.md`, without introducing hard rules
- `tests/test_server_architecture.py` — assert no `tools_core` import and no 11-tool surface assumptions
- `tests/test_v3_commands.py` — assert business command inventory and docs mention `docs/qmd-cli.md`
- `tests/test_no_retired_names.py` — ban the removed wrapper tool names in docs/skills/public surfaces
- `tests/test_v3_store.py` — assert write success and follow-up guidance without QMD side effects
- `tests/test_v3_health.py` — assert concept merge success and follow-up guidance without QMD side effects
- `tests/test_qmd_runtime.py` — trim to bootstrap-only collection/context tests
- `tests/test_cli.py` — assert bootstrap output reflects layout + QMD init only
- `tests/test_bootstrap_script.py` — keep direct v3 layout checks
- `tests/test_v3_core_tools.py` — replace or delete; its old wrapper-tool assertions are obsolete

## Task 1: Shrink The MCP Surface To Six Business Tools

**Files:**
- Delete: `server/tools_core.py`
- Modify: `server/server.py`
- Modify: `server/tools_knowledge.py`
- Modify: `tests/test_server_architecture.py`
- Modify: `tests/test_v3_commands.py`
- Delete or Rewrite: `tests/test_v3_core_tools.py`

- [ ] **Step 1: Write the failing surface tests**

```python
# tests/test_v3_commands.py
EXPECTED_MCP_TOOLS = {
    "discover_papers",
    "ingest_and_read",
    "check_concept_alias",
    "upsert_wiki_page",
    "merge_concept",
    "lint_vault",
}


def test_mcp_surface_exposes_business_tools_only() -> None:
    tools = asyncio.run(mcp.list_tools())
    names = {tool.name for tool in tools}
    assert names == EXPECTED_MCP_TOOLS
```

```python
# tests/test_server_architecture.py
assert set(import_specs) == {
    ("__future__", ("annotations",)),
    ("fastmcp", ("FastMCP",)),
    ("server.tools_health", ("register_health_tools",)),
    ("server.tools_intake", ("register_intake_tools",)),
    ("server.tools_knowledge", ("register_knowledge_tools",)),
}
assert set(call_names) == {
    "register_health_tools",
    "register_intake_tools",
    "register_knowledge_tools",
}
assert "tools_core" not in source
```

- [ ] **Step 2: Run the surface tests to verify they fail**

Run: `uv run pytest tests/test_v3_commands.py tests/test_server_architecture.py -q`

Expected: FAIL because `server/server.py` still imports and registers `tools_core`, and the MCP surface still exposes 11 tools.

- [ ] **Step 3: Remove the wrapper-tool registration layer**

```python
# server/server.py
"""Paper Distill v3 MCP entrypoint."""
from __future__ import annotations

from fastmcp import FastMCP

from server.tools_health import register_health_tools
from server.tools_intake import register_intake_tools
from server.tools_knowledge import register_knowledge_tools

mcp = FastMCP("paper-distill")

register_intake_tools(mcp)
register_knowledge_tools(mcp)
register_health_tools(mcp)


def main() -> None:
    mcp.run()
```

```python
# server/tools_knowledge.py
def register_knowledge_tools(mcp: FastMCP) -> None:
    mcp.tool(name="upsert_wiki_page")(upsert_wiki_page)
    mcp.tool(name="check_concept_alias")(check_concept_alias)
    mcp.tool(name="merge_concept")(merge_concept)
```

Delete `server/tools_core.py`.

If `tests/test_v3_core_tools.py` only exists to verify wrapper-tool behavior, delete it. If you prefer to keep the file, rewrite it to assert the six-tool surface and the absence of wrapper names instead of testing `kb_search`, `kb_get`, and `status`.

- [ ] **Step 4: Run the surface tests to verify they pass**

Run: `uv run pytest tests/test_v3_commands.py tests/test_server_architecture.py -q`

Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add server/server.py server/tools_knowledge.py tests/test_server_architecture.py tests/test_v3_commands.py
git rm server/tools_core.py
git rm tests/test_v3_core_tools.py || true
git commit -m "refactor: remove qmd wrapper mcp tools"
```

## Task 2: Trim QMD Runtime To Bootstrap-Only Initialization

**Files:**
- Modify: `server/qmd_runtime.py`
- Modify: `server/cli.py`
- Modify: `tests/test_qmd_runtime.py`
- Modify: `tests/test_cli.py`

- [ ] **Step 1: Write the failing bootstrap-only tests**

```python
# tests/test_qmd_runtime.py
def test_qmd_runtime_exports_bootstrap_helpers_only() -> None:
    source = Path("server/qmd_runtime.py").read_text(encoding="utf-8")
    assert "def ensure_qmd_ready" in source
    assert "def qmd_search" not in source
    assert "def qmd_get" not in source
    assert "def qmd_update" not in source
    assert "def qmd_reembed_force" not in source
```

```python
# tests/test_cli.py
def test_bootstrap_reports_layout_and_collection_init_only(...):
    payload = json.loads(stdout)
    assert "layout" in payload
    assert "qmd" in payload
    assert "collections" in payload["qmd"] or payload["qmd"]["status"] == "not_ready"
```

- [ ] **Step 2: Run the bootstrap tests to verify they fail**

Run: `uv run pytest tests/test_qmd_runtime.py tests/test_cli.py -q`

Expected: FAIL because `server/qmd_runtime.py` still exports read/index wrapper helpers.

- [ ] **Step 3: Remove runtime read/index wrappers and keep bootstrap support**

```python
# server/qmd_runtime.py
COLLECTIONS = {
    "canon-papers": ("wiki/papers", "Canonical distilled papers"),
    "canon-concepts": ("wiki/concepts", "Canonical concept pages"),
    "insights-conversations": ("insights/conversations", "Conversation-derived research insights"),
    "insights-ideas": ("insights/ideas", "Idea drafts and later validation assets"),
    "raw-evidence": ("raw/evidence", "Raw captured evidence and source markdown"),
}


def ensure_qmd_ready(vault_path: Path) -> dict[str, object]:
    ...


def qmd_ready_report(vault_path: Path) -> dict[str, object]:
    ...
```

Delete the old read/index wrapper functions:

- `qmd_search`
- `qmd_get`
- `qmd_update`
- `qmd_reembed_force`

Keep `server/cli.py` bootstrap behavior, but ensure its implementation only relies on:

- `ensure_v3_layout`
- `ensure_qmd_ready`
- `qmd_ready_report` or clear bootstrap error handling

If a rename to `server/qmd_bootstrap.py` makes the code clearer, perform that rename and update imports in `server/cli.py` and the bootstrap tests accordingly.

- [ ] **Step 4: Run the bootstrap tests to verify they pass**

Run: `uv run pytest tests/test_qmd_runtime.py tests/test_cli.py tests/test_bootstrap_script.py -q`

Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add server/qmd_runtime.py server/cli.py tests/test_qmd_runtime.py tests/test_cli.py tests/test_bootstrap_script.py
git commit -m "refactor: trim qmd runtime to bootstrap support"
```

## Task 3: Remove QMD Side Effects From Business Write Tools

**Files:**
- Modify: `server/v3_store.py`
- Modify: `server/v3_health.py`
- Modify: `tests/test_v3_store.py`
- Modify: `tests/test_v3_health.py`
- Modify: `server/tools_knowledge.py`

- [ ] **Step 1: Write the failing write-follow-up tests**

```python
# tests/test_v3_store.py
def test_upsert_wiki_page_returns_follow_up_guidance_without_running_qmd(...):
    result = upsert_wiki_page_v3(...)
    assert result["ok"] is True
    assert result["follow_up"] == [
        "Run qmd update after all writes in this round finish.",
        "Run qmd embed -f after all writes finish if semantic retrieval must reflect the new state immediately.",
    ]
```

```python
# tests/test_v3_health.py
def test_merge_concept_returns_follow_up_guidance_without_qmd_side_effects(...):
    result = merge_concept_v3(vault_path, "old", "new")
    assert result["ok"] is True
    assert result["follow_up"] == [
        "Run qmd update after all writes in this round finish.",
        "Run qmd embed -f after all writes finish if semantic retrieval must reflect the new state immediately.",
    ]
```

- [ ] **Step 2: Run the write tests to verify they fail**

Run: `uv run pytest tests/test_v3_store.py tests/test_v3_health.py -q`

Expected: FAIL because both implementations still call QMD helpers and return update/reembed side-effect results.

- [ ] **Step 3: Remove QMD calls and return follow-up reminders**

```python
# server/v3_store.py
FOLLOW_UP = [
    "Run qmd update after all writes in this round finish.",
    "Run qmd embed -f after all writes finish if semantic retrieval must reflect the new state immediately.",
]


def upsert_wiki_page_v3(...):
    ...
    atomic_write_text(path, render_markdown(payload, body))
    return {"ok": True, "path": str(path), "follow_up": list(FOLLOW_UP)}
```

```python
# server/v3_health.py
FOLLOW_UP = [
    "Run qmd update after all writes in this round finish.",
    "Run qmd embed -f after all writes finish if semantic retrieval must reflect the new state immediately.",
]


def merge_concept_v3(vault_path: Path, old: str, new: str) -> dict[str, Any]:
    ...
    return {
        "ok": True,
        "old": old,
        "new": new,
        "concept_path": str(concept_path),
        "rewritten_files": rewritten_files,
        "rewritten_links": rewritten_links,
        "alias_added": alias_added,
        "follow_up": list(FOLLOW_UP),
    }
```

Remove any imports of the deleted QMD runtime update/embed wrappers from `server/v3_store.py`, `server/v3_health.py`, and `server/tools_knowledge.py`.

- [ ] **Step 4: Run the write tests to verify they pass**

Run: `uv run pytest tests/test_v3_store.py tests/test_v3_health.py -q`

Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add server/v3_store.py server/v3_health.py server/tools_knowledge.py tests/test_v3_store.py tests/test_v3_health.py
git commit -m "refactor: remove qmd side effects from business writes"
```

## Task 4: Rewrite Docs, Skills, And Commands For Direct QMD CLI Usage

**Files:**
- Create: `docs/qmd-cli.md`
- Modify: `README.md`
- Modify: `docs/README.md`
- Modify: `docs/architecture.md`
- Modify: `docs/commands.md`
- Modify: `docs/installation.md`
- Modify: `docs/testing.md`
- Modify: `commands/discover.md`
- Modify: `commands/inbox.md`
- Modify: `commands/ingest.md`
- Modify: `commands/lint.md`
- Delete: `commands/get.md`
- Delete: `commands/search.md`
- Delete: `commands/status.md`
- Modify: `skills/paper-intake/SKILL.md`
- Modify: `skills/knowledge-workbench/SKILL.md`
- Modify: `skills/idea-workbench/SKILL.md`
- Modify: `skills/paper-intake/agents/openai.yaml`
- Modify: `skills/knowledge-workbench/agents/openai.yaml`
- Modify: `skills/idea-workbench/agents/openai.yaml`
- Modify: `hooks/session-start`
- Modify: `tests/test_v3_commands.py`
- Modify: `tests/test_no_retired_names.py`

- [ ] **Step 1: Write the failing doc/skill inventory tests**

```python
# tests/test_v3_commands.py
EXPECTED_COMMANDS = {"discover", "inbox", "ingest", "lint"}


def test_command_inventory_matches_business_surface_only() -> None:
    names = {path.stem for path in (REPO_ROOT / "commands").glob("*.md")}
    assert names == EXPECTED_COMMANDS


def test_public_docs_point_agents_to_qmd_cli_reference() -> None:
    readme = (REPO_ROOT / "README.md").read_text(encoding="utf-8")
    docs_readme = (REPO_ROOT / "docs/README.md").read_text(encoding="utf-8")
    assert "docs/qmd-cli.md" in readme
    assert "qmd-cli.md" in docs_readme
```

```python
# tests/test_no_retired_names.py
assert "kb_search" not in combined
assert "kb_get" not in combined
assert "kb_update_index" not in combined
assert "kb_reembed_force" not in combined
assert "docs/qmd-cli.md" in combined
assert "qmd --help" in combined
assert "qmd query" in combined
assert "qmd get" in combined
```

- [ ] **Step 2: Run the doc and skill tests to verify they fail**

Run: `uv run pytest tests/test_v3_commands.py tests/test_no_retired_names.py tests/test_skill_inventory.py -q`

Expected: FAIL because the repo still contains `commands/get.md`, `commands/search.md`, `commands/status.md`, and docs/skills still teach wrapper MCP tools.

- [ ] **Step 3: Add `docs/qmd-cli.md` and rewrite the public learning surface**

```markdown
# QMD CLI In Paper Distill

QMD CLI is the primary source; command details follow the runtime output of `qmd --help`.

## Collections

- `canon-papers` -> `wiki/papers`
- `canon-concepts` -> `wiki/concepts`
- `insights-conversations` -> `insights/conversations`
- `insights-ideas` -> `insights/ideas`
- `raw-evidence` -> `raw/evidence`

## Main Path

```bash
qmd --help
qmd query "vision-language-action" --json -c canon-papers -c canon-concepts
qmd get wiki/papers/example.md
qmd status
qmd update
qmd embed -f
```
```

Rewrite the skills so they explicitly say:

- use business MCP for `discover_papers`, `ingest_and_read`, `upsert_wiki_page`, `check_concept_alias`, `merge_concept`, `lint_vault`,
- use QMD CLI for `query`, `get`, `status`, `update`, and `embed`,
- consult `docs/qmd-cli.md`,
- consult runtime `qmd --help` when details are uncertain.

Delete `commands/get.md`, `commands/search.md`, and `commands/status.md`. Rewrite `docs/commands.md` so it only documents business command docs and points read/index tasks to `docs/qmd-cli.md`.

Keep `hooks/session-start` light. A suitable direction line is:

```bash
context_text="You have Paper Distill v3 installed. Use Paper Distill business skills for discovery, ingest, writing, concept maintenance, and linting. Use docs/qmd-cli.md and the runtime qmd CLI help for search, retrieval, collection health, update, and embed commands."
```

- [ ] **Step 4: Run the doc and skill tests to verify they pass**

Run: `uv run pytest tests/test_v3_commands.py tests/test_no_retired_names.py tests/test_skill_inventory.py -q`

Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add README.md docs/README.md docs/architecture.md docs/commands.md docs/installation.md docs/testing.md docs/qmd-cli.md commands/discover.md commands/inbox.md commands/ingest.md commands/lint.md skills/paper-intake/SKILL.md skills/knowledge-workbench/SKILL.md skills/idea-workbench/SKILL.md skills/paper-intake/agents/openai.yaml skills/knowledge-workbench/agents/openai.yaml skills/idea-workbench/agents/openai.yaml hooks/session-start tests/test_v3_commands.py tests/test_no_retired_names.py tests/test_skill_inventory.py
git rm commands/get.md commands/search.md commands/status.md
git commit -m "docs: teach qmd cli as the primary read path"
```

## Task 5: Final Cleanup And Full Verification

**Files:**
- Modify: any touched file only if verification exposes a real regression

- [ ] **Step 1: Run the focused boundary suite**

Run: `uv run pytest tests/test_server_architecture.py tests/test_qmd_runtime.py tests/test_cli.py tests/test_bootstrap_script.py tests/test_v3_store.py tests/test_v3_health.py tests/test_v3_commands.py tests/test_no_retired_names.py -q`

Expected: PASS

- [ ] **Step 2: Run the full suite**

Run: `uv run pytest -q`

Expected: PASS

- [ ] **Step 3: Run compile verification**

Run: `uv run python -m compileall -q server tests`

Expected: PASS with no output

- [ ] **Step 4: Run final MCP smoke and residue scans**

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
        "lint_vault",
        "merge_concept",
        "upsert_wiki_page",
    }
    assert set(names) == expected, names
    print(f"tool_count={len(names)}")

asyncio.run(main())
PY
```

Expected: `tool_count=6`

Run:

```bash
rg -n "kb_search|kb_get|kb_update_index|kb_reembed_force|status\\(" \
  server tests docs commands skills README.md
```

Expected: no matches in retained public surfaces except literal test guards that dynamically construct banned strings.

- [ ] **Step 5: Commit**

```bash
git add -A
git commit -m "refactor: make qmd cli the only read path"
```
