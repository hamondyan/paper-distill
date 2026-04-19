# Stateless Discovery Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make `/discover` return one-time chat results without creating, reading, or depending on `inbox/` or discovery approval state.

**Architecture:** Discovery becomes a pure search-and-rank operation that returns transient candidate dictionaries. The approval command/tool is retired from the public surface, and `/ingest approved` becomes an explicit unsupported workflow while direct arXiv ingest remains unchanged. Bootstrap, lint, agent capabilities, docs, and skills stop teaching or relying on inbox state.

**Tech Stack:** Python 3, FastMCP tool registration, pytest/unittest, Markdown command and skill docs, shell bootstrap script.

---

### Task 1: Make Discovery Stateless

**Files:**
- Modify: `tests/test_v3_discovery.py`
- Modify: `server/v3_discovery.py`

- [ ] **Step 1: Replace discovery tests with stateless behavior tests**

Replace `tests/test_v3_discovery.py` with:

```python
from __future__ import annotations

import asyncio

from server.v3_discovery import discover_papers_v3


def test_discover_papers_returns_ranked_chat_results_without_writing_vault(
    tmp_path, monkeypatch
) -> None:
    async def fake_search(*args, **kwargs):
        return [
            {
                "title": "Attention Is All You Need",
                "paper_id": "arxiv:1706.03762",
                "source_url": "https://arxiv.org/abs/1706.03762",
                "abstract": "Transformer paper.",
                "venue": "NeurIPS",
                "year": 2017,
                "authors": ["Ashish Vaswani", "Noam Shazeer"],
            }
        ]

    async def fake_score(*args, **kwargs):
        return [
            {
                "title": "Attention Is All You Need",
                "paper_id": "arxiv:1706.03762",
                "source_url": "https://arxiv.org/abs/1706.03762",
                "abstract": "Transformer paper.",
                "venue": "NeurIPS",
                "year": 2017,
                "authors": ["Ashish Vaswani", "Noam Shazeer"],
                "_score": 0.91,
                "_score_breakdown": {"topic_fit": 0.8},
                "best_topic": "sequence modeling",
            }
        ]

    def fail_layout(*args, **kwargs):
        raise AssertionError("discover_papers_v3 must not initialize vault layout")

    monkeypatch.setattr("server.v3_discovery.query_paper_sources_v3", fake_search)
    monkeypatch.setattr("server.v3_discovery.score_papers_v3", fake_score, raising=False)
    monkeypatch.setattr("server.v3_discovery.ensure_v3_layout", fail_layout, raising=False)

    result = asyncio.run(discover_papers_v3(query="transformer"))

    assert result["count"] == 1
    assert result["results"] == [
        {
            "paper_id": "arxiv:1706.03762",
            "title": "Attention Is All You Need",
            "score": 91,
            "source_url": "https://arxiv.org/abs/1706.03762",
            "abstract": "Transformer paper.",
            "venue": "NeurIPS",
            "year": 2017,
            "authors": ["Ashish Vaswani", "Noam Shazeer"],
            "best_topic": "sequence modeling",
            "score_breakdown": {"topic_fit": 0.8},
        }
    ]
    assert not (tmp_path / "inbox").exists()
    assert not (tmp_path / ".state" / "seen_papers.json").exists()


def test_discover_papers_scores_results_before_returning(monkeypatch) -> None:
    score_calls = []

    async def fake_search(*args, **kwargs):
        return [
            {
                "title": "Low Raw Score",
                "paper_id": "arxiv:2501.00001",
                "source_url": "https://arxiv.org/abs/2501.00001",
            }
        ]

    async def fake_score(papers):
        score_calls.append(papers)
        return [
            {
                "title": "Low Raw Score",
                "paper_id": "arxiv:2501.00001",
                "source_url": "https://arxiv.org/abs/2501.00001",
                "_score": 0.42,
            }
        ]

    monkeypatch.setattr("server.v3_discovery.query_paper_sources_v3", fake_search)
    monkeypatch.setattr("server.v3_discovery.score_papers_v3", fake_score, raising=False)

    result = asyncio.run(discover_papers_v3(query="robotics"))

    assert len(score_calls) == 1
    assert result["results"][0]["score"] == 42


def test_discover_papers_is_stateless_between_runs(monkeypatch) -> None:
    async def fake_search(*args, **kwargs):
        return [
            {
                "title": "Repeatable Candidate",
                "paper_id": "arxiv:2501.00002",
                "source_url": "https://arxiv.org/abs/2501.00002",
            }
        ]

    async def fake_score(papers):
        return [dict(papers[0], _score=0.7)]

    monkeypatch.setattr("server.v3_discovery.query_paper_sources_v3", fake_search)
    monkeypatch.setattr("server.v3_discovery.score_papers_v3", fake_score, raising=False)

    first = asyncio.run(discover_papers_v3(query="robotics"))
    second = asyncio.run(discover_papers_v3(query="robotics"))

    assert first["results"] == second["results"]
    assert first["results"][0]["paper_id"] == "arxiv:2501.00002"


def test_discover_papers_skips_items_without_identity_or_title(monkeypatch) -> None:
    async def fake_search(*args, **kwargs):
        return []

    async def fake_score(*args, **kwargs):
        return [
            {"paper_id": "", "title": "Missing ID", "_score": 1.0},
            {"paper_id": "arxiv:2501.00003", "title": "", "_score": 1.0},
            {
                "paper_id": "arxiv:2501.00004",
                "title": "Complete",
                "source_url": "https://arxiv.org/abs/2501.00004",
                "_score": 0.5,
            },
        ]

    monkeypatch.setattr("server.v3_discovery.query_paper_sources_v3", fake_search)
    monkeypatch.setattr("server.v3_discovery.score_papers_v3", fake_score, raising=False)

    result = asyncio.run(discover_papers_v3(query="robotics"))

    assert [item["paper_id"] for item in result["results"]] == ["arxiv:2501.00004"]
```

- [ ] **Step 2: Run discovery tests and verify they fail**

Run:

```bash
uv run python -m pytest tests/test_v3_discovery.py -q
```

Expected: tests fail because `discover_papers_v3` still writes inbox stubs and returns `saved` / `skipped_seen`.

- [ ] **Step 3: Implement transient discovery results**

Replace `server/v3_discovery.py` with:

```python
from __future__ import annotations

from typing import Any

from server.config import ConfigError
from server.paper_utils import canonical_item_url
from server.v3_scoring import query_paper_sources_v3, score_papers_v3


def _paper_source_url(paper: dict[str, Any]) -> str:
    return str(
        paper.get("source_url")
        or paper.get("canonical_item_url")
        or canonical_item_url(paper)
        or ""
    ).strip()


def _paper_score(paper: dict[str, Any]) -> int:
    raw_score = paper.get("_score", 0)
    try:
        numeric = float(raw_score)
    except (TypeError, ValueError):
        return 0
    if 0 <= numeric <= 1:
        numeric *= 100
    return int(round(numeric))


def _string_list(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(item).strip() for item in value if str(item).strip()]


def _candidate_result(paper: dict[str, Any]) -> dict[str, Any] | None:
    pid = str(paper.get("paper_id", "")).strip()
    title = str(paper.get("title", "")).strip()
    if not pid or not title:
        return None

    result: dict[str, Any] = {
        "paper_id": pid,
        "title": title,
        "score": _paper_score(paper),
        "source_url": _paper_source_url(paper),
    }
    for key in ("abstract", "venue", "year", "best_topic"):
        value = paper.get(key)
        if value not in (None, ""):
            result[key] = value
    authors = _string_list(paper.get("authors"))
    if authors:
        result["authors"] = authors
    breakdown = paper.get("_score_breakdown")
    if isinstance(breakdown, dict):
        result["score_breakdown"] = breakdown
    return result


async def discover_papers_v3(query: str | None = None) -> dict[str, Any]:
    try:
        results = await query_paper_sources_v3(query=query or "", sources=None, max_results=20)
        scored_results = await score_papers_v3(results)
    except ConfigError as exc:
        return {"error": str(exc)}

    candidates = [
        candidate
        for paper in scored_results
        if (candidate := _candidate_result(paper)) is not None
    ]
    return {"results": candidates, "count": len(candidates)}
```

- [ ] **Step 4: Run discovery tests and verify they pass**

Run:

```bash
uv run python -m pytest tests/test_v3_discovery.py -q
```

Expected: all tests in `tests/test_v3_discovery.py` pass.

- [ ] **Step 5: Commit discovery change**

Run:

```bash
git add tests/test_v3_discovery.py server/v3_discovery.py
git commit -m "feat: return stateless discovery results"
```

Expected: commit succeeds.

### Task 2: Retire Approval Ingest Path

**Files:**
- Modify: `tests/test_v3_ingest.py`
- Delete: `tests/test_v3_approval.py`
- Modify: `server/v3_ingest.py`
- Modify: `server/tools_intake.py`
- Delete: `server/v3_approval.py`

- [ ] **Step 1: Add failing ingest and tool-surface tests**

In `tests/test_v3_ingest.py`, remove approved-inbox mode tests and keep direct-ingest tests. Add this test inside `V3IngestTest`:

```python
    def test_approved_input_is_retired_and_does_not_scan_inbox(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            vault_root = Path(tmpdir)
            inbox_dir = vault_root / "inbox"
            inbox_dir.mkdir(parents=True)
            inbox_dir.joinpath("approved.md").write_text(
                """---
paper_id: arxiv:2501.00001
title: Approved Paper
source_url: https://arxiv.org/abs/2501.00001
---

#approved
""",
                encoding="utf-8",
            )

            with patch("server.v3_ingest.get_vault_path", return_value=tmpdir):
                with patch("server.v3_ingest.ensure_v3_layout", return_value={"created": []}):
                    with patch("server.v3_ingest.capture_arxiv_source", new=AsyncMock()) as capture_mock:
                        from server.v3_ingest import ingest_and_read_v3

                        result = asyncio.run(ingest_and_read_v3("approved"))

            self.assertFalse(result["ok"])
            self.assertEqual(result["items"], [])
            self.assertEqual(result["errors"], [])
            self.assertIn("retired", result["error"])
            self.assertIn("arXiv", result["error"])
            self.assertEqual(capture_mock.await_count, 0)
```

Delete `tests/test_v3_approval.py`; approval is no longer a supported tool surface.

- [ ] **Step 2: Run focused ingest tests and verify failure**

Run:

```bash
uv run python -m pytest tests/test_v3_ingest.py -q
```

Expected: the new approved-input test fails because `ingest_and_read_v3("approved")` still scans inbox notes.

- [ ] **Step 3: Implement retired `approved` input and remove approval tool registration**

In `server/v3_ingest.py`:

Remove this import:

```python
from server.v3_approval import _approved_body
```

Remove `_approved_inbox_papers` and `_approved_error`.

Add this constant near `_DIRECT_RESOLUTION_ERROR`:

```python
_APPROVED_WORKFLOW_RETIRED_ERROR = (
    "The legacy approval ingest workflow is retired. "
    "Pass resolved arXiv URLs, arXiv IDs, or arXiv DOI values to /ingest instead."
)
```

Replace the `if input_value == "approved":` branch with:

```python
    if input_value == "approved":
        return {
            "ok": False,
            "error": _APPROVED_WORKFLOW_RETIRED_ERROR,
            "items": [],
            "errors": [],
            "captured_count": 0,
            "error_count": 0,
        }
```

In `server/tools_intake.py`, remove `asyncio`, `Path`, `ConfigError`, `get_vault_path`, and `approve_papers_v3` imports. Remove the `approve_papers` function. Change registration to:

```python
def register_intake_tools(mcp: FastMCP) -> None:
    mcp.tool(name="discover_papers")(discover_papers)
    mcp.tool(name="ingest_and_read")(ingest_and_read)
```

Delete `server/v3_approval.py`; no runtime code should import approval helpers after the ingest branch stops scanning approval notes.

- [ ] **Step 4: Run ingest tests and MCP surface tests**

Run:

```bash
uv run python -m pytest tests/test_v3_ingest.py tests/test_v3_commands.py -q
```

Expected: ingest tests pass; `tests/test_v3_commands.py` still fails until Task 4 updates the expected public command/tool surface.

- [ ] **Step 5: Commit retired approval ingest code**

Run:

```bash
git add tests/test_v3_ingest.py tests/test_v3_approval.py server/v3_ingest.py server/tools_intake.py server/v3_approval.py
git commit -m "feat: retire approved inbox ingest"
```

Expected: commit succeeds.

### Task 3: Remove Inbox From Bootstrap and Lint

**Files:**
- Modify: `tests/test_v3_bootstrap.py`
- Modify: `tests/test_bootstrap_script.py`
- Modify: `tests/test_v3_health.py`
- Modify: `server/v3_bootstrap.py`
- Modify: `scripts/bootstrap.sh`
- Modify: `server/v3_health.py`

- [ ] **Step 1: Update bootstrap and lint tests**

In `tests/test_v3_bootstrap.py`, change the assertions to:

```python
from server.v3_bootstrap import ensure_v3_layout, paper_filename


def test_ensure_v3_layout_creates_empty_vault_tree(tmp_path):
    result = ensure_v3_layout(tmp_path)

    assert not (tmp_path / "inbox").exists()
    assert (tmp_path / "raw" / "evidence").is_dir()
    assert (tmp_path / "wiki" / "papers").is_dir()
    assert (tmp_path / "wiki" / "concepts").is_dir()
    assert (tmp_path / "insights" / "ideas").is_dir()
    assert (tmp_path / "insights" / "conversations").is_dir()
    assert (tmp_path / "exports" / "presentations").is_dir()
    assert (tmp_path / ".state").is_dir()
    assert not (tmp_path / ".state" / "seen_papers.json").exists()
    assert (tmp_path / "vault-log.md").exists()
    assert paper_filename("Attention Is All You Need", "arxiv:1706.03762") == "attention-is-all-you-need--arxiv-1706.03762.md"
    assert paper_filename("A Study", "doi:10.1145/123/456") == "a-study--doi-10.1145-123-456.md"
    assert result["created"]
```

In `tests/test_bootstrap_script.py`, replace the directory list with:

```python
        for rel_path in (
            "raw/evidence",
            "wiki/papers",
            "wiki/concepts",
            "insights/ideas",
            "insights/conversations",
            "exports/presentations",
            ".state",
            "vault-log.md",
        ):
            assert (root / rel_path).exists()

        assert not (root / "inbox").exists()
        assert not (root / ".state" / "seen_papers.json").exists()
```

In `tests/test_v3_health.py`, remove `INBOX_STALE_DAYS` from the import and replace `test_lint_vault_flags_stale_inbox_notes` with:

```python
def test_lint_vault_ignores_retired_inbox_notes(tmp_path: Path) -> None:
    inbox_dir = tmp_path / "inbox"
    inbox_dir.mkdir(parents=True)
    inbox_dir.joinpath("stale.md").write_text(
        '---\ntype: inbox_stub\ndiscovered_at: "2025-01-01"\n---\n\nsome note\n',
        encoding="utf-8",
    )

    result = lint_vault_v3(tmp_path, today=date(2026, 4, 18))

    assert not any(i["code"] == "inbox_stale" for i in result["issues"])
```

- [ ] **Step 2: Run bootstrap and health tests and verify failure**

Run:

```bash
uv run python -m pytest tests/test_v3_bootstrap.py tests/test_bootstrap_script.py tests/test_v3_health.py -q
```

Expected: tests fail because bootstrap still creates `inbox/` and `.state/seen_papers.json`, and lint still reports `inbox_stale`.

- [ ] **Step 3: Implement bootstrap and lint changes**

In `server/v3_bootstrap.py`, change `V3_DIRS` to:

```python
V3_DIRS = (
    "raw/evidence",
    "wiki/papers",
    "wiki/concepts",
    "insights/ideas",
    "insights/conversations",
    "exports/presentations",
    ".state",
)
```

Remove the `seen_path` block from `ensure_v3_layout`.

In `scripts/bootstrap.sh`, remove:

```bash
mkdir -p "${VAULT_PATH}/inbox"
if [[ ! -f "${VAULT_PATH}/.state/seen_papers.json" ]]; then
  cat > "${VAULT_PATH}/.state/seen_papers.json" << 'EOF'
{}
EOF
fi
echo "  inbox/"
echo "  .state/seen_papers.json"
```

Keep `mkdir -p "${VAULT_PATH}/.state"` and keep the existing raw/wiki/insights/export/vault-log behavior.

In `server/v3_health.py`, change the date import from:

```python
from datetime import date, datetime, timedelta
```

to:

```python
from datetime import date
```

Delete the `INBOX_STALE_DAYS = 30` constant. Delete the complete `_parse_discovered_at` function and the complete `_inbox_stale_issues` function. In `lint_vault_v3`, delete this call:

```python
issues.extend(_inbox_stale_issues(vault_path, today or date.today(), INBOX_STALE_DAYS))
```

Keep `lint_vault_v3(vault_path, *, today: date | None = None)` so callers and tests remain source-compatible, but do not use `today` for inbox checks.

- [ ] **Step 4: Run bootstrap and health tests and verify pass**

Run:

```bash
uv run python -m pytest tests/test_v3_bootstrap.py tests/test_bootstrap_script.py tests/test_v3_health.py -q
```

Expected: all targeted tests pass.

- [ ] **Step 5: Commit bootstrap and lint changes**

Run:

```bash
git add tests/test_v3_bootstrap.py tests/test_bootstrap_script.py tests/test_v3_health.py server/v3_bootstrap.py scripts/bootstrap.sh server/v3_health.py
git commit -m "feat: remove inbox from vault layout"
```

Expected: commit succeeds.

### Task 4: Update Config, Capabilities, Commands, and Public Surface Tests

**Files:**
- Modify: `settings.example.json`
- Modify: `server/config.py`
- Modify: `server/agent_capabilities.py`
- Modify: `tests/test_config.py`
- Modify: `tests/test_agent_capabilities.py`
- Modify: `tests/test_v3_commands.py`
- Modify: `commands/discover.md`
- Modify: `commands/ingest.md`
- Delete: `commands/approve.md`

- [ ] **Step 1: Update public surface tests**

In `tests/test_v3_commands.py`, change the top constants to:

```python
EXPECTED_COMMANDS = {"discover", "ingest", "lint", "status"}
EXPECTED_MCP_TOOLS = {
    "discover_papers",
    "ingest_and_read",
    "distill_paper",
    "distill_papers",
    "check_concept_alias",
    "upsert_wiki_page",
    "merge_concept",
    "lint_vault",
}
```

In `test_public_command_docs_point_to_v3_tools`, remove `approve_doc` reads and approval assertions. Change the ingest assertion to:

```python
    assert 'argument-hint: "[arxiv-url | arxiv-id | arxiv-doi | paper-title]"' in ingest_doc
    assert "approved" not in ingest_doc
```

In `test_public_docs_describe_v3_qmd_cutover`, replace assertions that mention approval/inbox counts with:

```python
    assert "chat-only discovery" in readme
    assert "discover -> ingest resolved arXiv references -> distill_paper -> qmd update -> lint" in architecture
    assert "/approve" not in commands
    assert "papers, concepts, ideas, conversations, raw evidence" in commands
    assert "inbox pending" not in commands
```

In `tests/test_agent_capabilities.py`, change the routing assertion to:

```python
    assert "Find new papers: call discover_papers for chat-only candidates, not qmd query." in context
```

In `tests/test_config.py`, remove `"detailed_inbox_cards": True` from `_valid_settings()["paper_distill"]["workflow"]`. Add this assertion to `test_load_settings_returns_validated_settings_without_python_fallbacks`:

```python
    assert "detailed_inbox_cards" not in settings["workflow"]
```

- [ ] **Step 2: Run public surface tests and verify failure**

Run:

```bash
uv run python -m pytest tests/test_v3_commands.py tests/test_agent_capabilities.py tests/test_config.py -q
```

Expected: tests fail because command docs, MCP surface, capabilities, and config still expose approval/inbox language.

- [ ] **Step 3: Update runtime config and capability inventory**

In `server/config.py`, remove the `detailed_inbox_cards` entry from the returned `"workflow"` dictionary. Leave the `workflow` object itself and the other workflow keys in place.

In `settings.example.json`, remove:

```json
"detailed_inbox_cards": true,
```

Change capture failure policy to a non-inbox value:

```json
"failure_policy": "report_error",
```

In `tests/test_config.py`, change `_valid_settings()["paper_distill"]["capture"]["failure_policy"]` to `"report_error"`.

In `server/agent_capabilities.py`:

```python
{
    "name": "paper-intake",
    "use_when": "discovering chat-only paper candidates or ingesting resolved arXiv evidence",
}
```

Remove the `/approve` command entry. Change `/ingest` to:

```python
{"name": "/ingest", "use_when": "capture resolved arXiv papers", "backing": "ingest_and_read"}
```

Change MCP tool entries to:

```python
{"name": "discover_papers", "use_when": "find new papers and return chat-only candidates"},
{"name": "ingest_and_read", "use_when": "capture resolved arXiv identities"},
```

Change routing to:

```python
{"name": "Find new papers", "use_when": "call discover_papers for chat-only candidates, not qmd query."},
```

- [ ] **Step 4: Update slash command docs**

Delete `commands/approve.md`.

Replace `commands/discover.md` with:

```markdown
---
description: Use when the user wants to find new papers, pull a daily digest, or search arXiv/Semantic Scholar/OpenAlex for a research topic. Runs stateless v3 discovery and returns chat-only candidates.
argument-hint: "[query]"
---

Call `discover_papers` to run the v3 discovery flow.

This searches paper sources, scores and ranks candidates, and returns the results directly to the agent for presentation in chat. It does not write `inbox/`, update a seen cache, approve papers, or ingest anything.

After discovery, help the user choose candidates from the current chat result. To capture a paper, resolve the chosen item to an arXiv URL, arXiv ID, or arXiv DOI and call `/ingest` with that resolved identity.
```

Replace the frontmatter and first section of `commands/ingest.md` with:

```markdown
---
description: Use when the user wants to capture one or more resolved arXiv URLs, IDs, DOIs, or paper titles/acronyms. Writes raw evidence to raw/evidence/.
argument-hint: "[arxiv-url | arxiv-id | arxiv-doi | paper-title]"
---

Use the v3 `ingest_and_read` tool to capture raw evidence.

The agent resolves user-provided paper references to arXiv identities first. The MCP call should receive one or multiple resolved arXiv URLs, arXiv IDs, or arXiv DOI values and capture those papers into `raw/evidence/`. The MCP tool does not search arbitrary names by itself.
```

Remove examples and prose that mention `/ingest approved`.

- [ ] **Step 5: Run public surface tests and verify pass**

Run:

```bash
uv run python -m pytest tests/test_v3_commands.py tests/test_agent_capabilities.py tests/test_config.py -q
```

Expected: all targeted tests pass.

- [ ] **Step 6: Commit public surface changes**

Run:

```bash
git add settings.example.json server/config.py server/agent_capabilities.py tests/test_config.py tests/test_agent_capabilities.py tests/test_v3_commands.py commands/discover.md commands/ingest.md commands/approve.md
git commit -m "feat: retire approval command surface"
```

Expected: commit succeeds.

### Task 5: Update Docs and Skills

**Files:**
- Modify: `CLAUDE.md`
- Modify: `README.md`
- Modify: `docs/README.md`
- Modify: `docs/architecture.md`
- Modify: `docs/commands.md`
- Modify: `docs/configuration.md`
- Modify: `docs/frontmatter-reference.md`
- Modify: `docs/vault-layout.md`
- Modify: `docs/testing.md`
- Modify: `docs/qmd-cli.md`
- Modify: `skills/paper-intake/SKILL.md`
- Modify: `skills/paper-intake/agents/openai.yaml`
- Modify: `skills/paper-intake/references/ingest-rules.md`
- Modify: `skills/paper-intake/references/post-discovery-rescoring.md`
- Modify: `skills/paper-intake/references/approval-rules.md`
- Modify: `skills/knowledge-workbench/references/health-maintenance.md`
- Modify: `tests/test_no_retired_names.py`
- Modify: `tests/test_v3_commands.py`

- [ ] **Step 1: Update docs and skill tests for the new language**

In `tests/test_no_retired_names.py`, change `test_skills_route_through_v3_tools_only` so paper-intake asserts:

```python
    assert "discover_papers" in skill_docs["paper-intake"]
    assert "ingest_and_read" in skill_docs["paper-intake"]
    assert "chat-only" in skill_docs["paper-intake"]
    assert "raw/evidence" in skill_docs["paper-intake"]
    assert "docs/qmd-cli.md" in skill_docs["paper-intake"]
    assert "qmd --help" in skill_docs["paper-intake"]
    assert "#approved" not in skill_docs["paper-intake"]
```

In `tests/test_v3_commands.py`, keep the Task 4 doc assertions and add:

```python
    assert "inbox/" not in readme
    assert "seen_papers.json" not in vault_layout
    assert "Inbox Stub" not in frontmatter
```

- [ ] **Step 2: Run docs and skill tests and verify failure**

Run:

```bash
uv run python -m pytest tests/test_no_retired_names.py tests/test_v3_commands.py -q
```

Expected: tests fail because docs and skills still teach inbox and approval.

- [ ] **Step 3: Update root guidance and README**

In `CLAUDE.md`, change the core flow to:

```text
/discover -> agent presents chat-only candidates -> /ingest <resolved arXiv identity> -> paper-distillation skill or distill_paper writes wiki page -> /lint
```

Change the skill line to:

```markdown
- `paper-intake` — chat-only discovery and capture of resolved arXiv identities to `raw/evidence/`.
```

In `README.md`, use these product statements:

```markdown
- discovery returns chat-only candidates instead of writing a review inbox
- the agent helps resolve selected candidates to arXiv identities for direct capture
- ingest resolved arXiv references into `raw/evidence/`
```

Use this flow:

```text
/discover -> /ingest <resolved arXiv identity> -> distill_paper -> qmd update -> /lint
```

Remove `/approve`, `/ingest approved`, and `inbox/` from the user-facing command and layout sections.

- [ ] **Step 4: Update docs under `docs/`**

Use this wording in the relevant files:

```markdown
Discovery is chat-only. `discover_papers(query=None)` returns ranked transient candidates for the agent to present, and it does not write vault files or candidate state.
```

Use this command flow in `docs/architecture.md` and `docs/commands.md`:

```text
discover -> ingest resolved arXiv references -> distill_paper -> qmd update -> lint
```

In `docs/vault-layout.md`, the tree should include:

```text
vault/
├── raw/evidence/
├── wiki/papers/
├── wiki/concepts/
├── insights/ideas/
├── insights/conversations/
├── exports/presentations/
├── .state/
└── vault-log.md
```

In `docs/frontmatter-reference.md`, remove the entire "Inbox Stub" section. Keep raw evidence, paper, concept, idea, and conversation frontmatter.

In `docs/configuration.md`, remove `workflow.detailed_inbox_cards` and change `workflow` description to:

```markdown
| `workflow` | object | Discovery selection and candidate shaping behavior. |
```

In `docs/commands.md`, remove `/approve`, `/ingest approved`, `inbox_stale`, and inbox counts from status docs.

In `docs/qmd-cli.md`, change "approved ingest" to "direct ingest" in the Paper Distill MCP sentence.

- [ ] **Step 5: Update paper-intake skill docs**

In `skills/paper-intake/SKILL.md`, use this routing table:

```markdown
| Tool | Use |
| --- | --- |
| `discover_papers` | Search, score, and return chat-only candidates |
| `ingest_and_read` | Capture one or many agent-resolved arXiv identities |
```

Use this decision tree:

```markdown
1. User asked for discovery without asking to ingest specific papers: call `discover_papers(query=...)`, present the returned candidates in chat, and stop.
2. User picked a candidate from the current conversation: resolve it to an arXiv URL, arXiv ID, or arXiv DOI, then call `ingest_and_read(input_value=...)`.
3. User supplied direct arXiv URLs, IDs, or arXiv DOI values: call `ingest_and_read(input_value=...)`.
4. User supplied natural paper names: resolve names to arXiv identities first; do not pass unresolved names to the MCP tool.
```

Replace approval rules with:

```markdown
- Discovery is transient. Do not promise that candidates were saved for later approval.
- Ingest captures only. `ingest_and_read` accepts arXiv URLs, arXiv IDs, or arXiv DOI values after agent resolution.
- If the user asks to approve papers, explain that approval inboxes are retired and ask which resolved paper identity they want to ingest.
```

In `skills/paper-intake/references/post-discovery-rescoring.md`, change the reference to say re-scoring is agent-side presentation guidance over the returned `results`, and remove instructions to append `rescore_reason` to inbox files.

In `skills/paper-intake/references/approval-rules.md`, replace the body with a short retired-workflow note that avoids legacy command names:

```markdown
# Retired Approval Workflow

Paper Distill no longer uses persisted approval markers or a separate approval command.

When a user says they approve a discovered paper, resolve that paper to an arXiv URL, arXiv ID, or arXiv DOI and call `ingest_and_read` with the resolved identity.
```

In `skills/paper-intake/references/ingest-rules.md`, remove `ingest_and_read(input_value="approved")` and keep the resolved/unresolved direct ingest contract.

- [ ] **Step 6: Run docs and skill tests and verify pass**

Run:

```bash
uv run python -m pytest tests/test_no_retired_names.py tests/test_v3_commands.py -q
```

Expected: all targeted docs and skill tests pass.

- [ ] **Step 7: Commit docs and skill changes**

Run:

```bash
git add CLAUDE.md README.md docs commands skills tests/test_no_retired_names.py tests/test_v3_commands.py
git commit -m "docs: describe chat-only discovery"
```

Expected: commit succeeds.

### Task 6: Final Verification

**Files:**
- Verify the whole repository.

- [ ] **Step 1: Run full test suite**

Run:

```bash
uv run python -m pytest -q
```

Expected: all tests pass.

- [ ] **Step 2: Run compile check**

Run:

```bash
uv run python -m compileall -q server tests
```

Expected: command exits successfully with no output.

- [ ] **Step 3: Search for retired inbox workflow references**

Run:

```bash
rg -n "inbox|#approved|approve_papers|/approve|ingest approved|seen_papers|inbox_stale|detailed_inbox_cards|return_to_inbox" README.md CLAUDE.md commands docs skills server settings.example.json scripts -S -g '!docs/superpowers/**'
```

Expected: no references remain in the public docs, skill docs, runtime code, settings example, or bootstrap scripts. Legacy terms may remain in tests that prove the retired input does not scan old files, and in historical process artifacts under `docs/superpowers/`.

- [ ] **Step 4: Inspect git status**

Run:

```bash
git status --short
```

Expected: clean working tree after all task commits.
