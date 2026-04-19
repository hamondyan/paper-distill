# Paper Distill Root-As-Plugin Marketplace Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a repo-local Codex marketplace entry for `paper-distill` while keeping the repository root as the plugin root.

**Architecture:** Add a repo-owned marketplace file at `.agents/plugins/marketplace.json` and make the `paper-distill` entry point at `./` instead of `./plugins/paper-distill`. Keep `.codex-plugin/plugin.json` as the runtime manifest, then update user-facing docs and regression tests so the root-as-plugin exception is explicit and stable.

**Tech Stack:** JSON manifests, Markdown docs, Python pytest

---

### Task 1: Add The Repo-Local Marketplace Entry

**Files:**
- Create: `.agents/plugins/marketplace.json`
- Modify: `tests/test_plugin_layout.py`

- [ ] **Step 1: Write the failing test**

```python
import json


def test_repo_local_marketplace_entry_points_at_root_plugin() -> None:
    marketplace = json.loads((REPO_ROOT / ".agents" / "plugins" / "marketplace.json").read_text(encoding="utf-8"))
    entry = next(plugin for plugin in marketplace["plugins"] if plugin["name"] == "paper-distill")

    assert entry["source"]["source"] == "local"
    assert entry["source"]["path"] == "./"
    assert entry["policy"]["installation"] == "AVAILABLE"
    assert entry["policy"]["authentication"] == "ON_INSTALL"
    assert entry["category"] == "Productivity"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run --with pytest python -m pytest tests/test_plugin_layout.py::test_repo_local_marketplace_entry_points_at_root_plugin -q`
Expected: FAIL with `FileNotFoundError` because `.agents/plugins/marketplace.json` does not exist yet

- [ ] **Step 3: Write minimal implementation**

Create `.agents/plugins/marketplace.json` with:

```json
{
  "name": "paper-distill-local",
  "interface": {
    "displayName": "Paper Distill Local"
  },
  "plugins": [
    {
      "name": "paper-distill",
      "source": {
        "source": "local",
        "path": "./"
      },
      "policy": {
        "installation": "AVAILABLE",
        "authentication": "ON_INSTALL"
      },
      "category": "Productivity"
    }
  ]
}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run --with pytest python -m pytest tests/test_plugin_layout.py::test_repo_local_marketplace_entry_points_at_root_plugin -q`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add .agents/plugins/marketplace.json tests/test_plugin_layout.py
git commit -m "feat: add repo-local marketplace entry"
```

### Task 2: Explain The Root Marketplace Exception In User Docs

**Files:**
- Modify: `README.md`
- Modify: `docs/plugin-installation.md`
- Modify: `tests/test_plugin_layout.py`

- [ ] **Step 1: Write the failing test**

```python
def test_root_marketplace_docs_explain_repo_local_discovery() -> None:
    readme = (REPO_ROOT / "README.md").read_text(encoding="utf-8")
    installation = (REPO_ROOT / "docs" / "plugin-installation.md").read_text(encoding="utf-8")

    assert "repo-local marketplace" in readme
    assert ".agents/plugins/marketplace.json" in installation
    assert "points at `./`" in installation
    assert "Codex can install Paper Distill from the repo-local marketplace entry" in installation
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run --with pytest python -m pytest tests/test_plugin_layout.py::test_root_marketplace_docs_explain_repo_local_discovery -q`
Expected: FAIL because the current docs describe local plugin registration but not the repo-local marketplace exception

- [ ] **Step 3: Write minimal implementation**

Add this sentence to the plugin section in `README.md`:

```markdown
Codex can also discover Paper Distill from the repo-local marketplace at `.agents/plugins/marketplace.json`, where the `paper-distill` entry intentionally points at the repository root.
```

Update `docs/plugin-installation.md` so the Codex install note reads:

```markdown
## Install

- Codex: install Paper Distill from the repo-local marketplace entry at `.agents/plugins/marketplace.json`, where `paper-distill` intentionally points at `./` so Codex resolves the repository root as the plugin root. Direct local registration through `.codex-plugin/plugin.json` still works.
```

Keep the Claude and OpenClaw sections intact.

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run --with pytest python -m pytest tests/test_plugin_layout.py::test_root_marketplace_docs_explain_repo_local_discovery -q`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add README.md docs/plugin-installation.md tests/test_plugin_layout.py
git commit -m "docs: explain repo-local marketplace install"
```

### Task 3: Document Verification And Run The Full Suite

**Files:**
- Modify: `docs/testing.md`
- Modify: `tests/test_plugin_layout.py`

- [ ] **Step 1: Write the failing test**

```python
def test_testing_docs_include_repo_marketplace_check() -> None:
    testing = (REPO_ROOT / "docs" / "testing.md").read_text(encoding="utf-8")

    assert "repo-local marketplace" in testing
    assert "tests/test_plugin_layout.py -q" in testing
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run --with pytest python -m pytest tests/test_plugin_layout.py::test_testing_docs_include_repo_marketplace_check -q`
Expected: FAIL because `docs/testing.md` does not mention the repo-local marketplace verification path yet

- [ ] **Step 3: Write minimal implementation**

Add a short subsection to `docs/testing.md`:

```markdown
## Repo-Local Marketplace Check

Run:

    uv run --with pytest python -m pytest tests/test_plugin_layout.py -q

This check covers the root-as-plugin manifests, hook launch path, and the repo-local marketplace entry that points at `./`.
```

- [ ] **Step 4: Run the verification commands**

Run: `uv run --with pytest python -m pytest tests/test_plugin_layout.py -q`
Expected: PASS

Run: `uv run --with pytest python -m pytest -q`
Expected: PASS

Run: `uv run python -m compileall -q server tests`
Expected: exit code 0

- [ ] **Step 5: Commit**

```bash
git add docs/testing.md tests/test_plugin_layout.py
git commit -m "test: cover root marketplace behavior"
```
