# Paper Distill Cross-Host Plugin Hardening Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Harden `paper-distill` as a root-as-plugin Codex plugin while preserving Claude and OpenClaw compatibility through one shared runtime.

**Architecture:** Keep the repository root as the canonical plugin root. Preserve `.codex-plugin/plugin.json`, `.claude-plugin/plugin.json`, and `.mcp.json`, but centralize plugin-root resolution in a shared script and make hooks host-neutral. Add installation documentation and regression tests around manifest and root-resolution behavior.

**Tech Stack:** Shell scripts, JSON manifests, Markdown docs, Python pytest

---

### Task 1: Add Shared Plugin-Root Resolution

**Files:**
- Create: `scripts/plugin-root.sh`
- Modify: `scripts/run-mcp.sh`
- Test: `tests/test_plugin_layout.py`

- [ ] **Step 1: Write the failing test**

```python
from pathlib import Path


def test_mcp_launcher_uses_shared_root_helper() -> None:
    launcher = Path("scripts/run-mcp.sh").read_text(encoding="utf-8")
    assert "plugin-root.sh" in launcher
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run python -m pytest tests/test_plugin_layout.py::test_mcp_launcher_uses_shared_root_helper -q`
Expected: FAIL because `tests/test_plugin_layout.py` does not exist yet and `run-mcp.sh` does not call the helper

- [ ] **Step 3: Write minimal implementation**

```bash
#!/usr/bin/env bash
set -euo pipefail

if [[ -n "${CLAUDE_PLUGIN_ROOT:-}" ]]; then
  printf '%s\n' "${CLAUDE_PLUGIN_ROOT}"
elif [[ -n "${CODEX_PLUGIN_ROOT:-}" ]]; then
  printf '%s\n' "${CODEX_PLUGIN_ROOT}"
elif [[ -n "${OPENCLAW_PLUGIN_ROOT:-}" ]]; then
  printf '%s\n' "${OPENCLAW_PLUGIN_ROOT}"
else
  SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
  printf '%s\n' "$(cd "${SCRIPT_DIR}/.." && pwd)"
fi
```

Update `scripts/run-mcp.sh` to resolve `REPO_ROOT="$("${SCRIPT_DIR}/plugin-root.sh")"` and run `uv --directory "${REPO_ROOT}" run paper-distill-server`.

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run python -m pytest tests/test_plugin_layout.py::test_mcp_launcher_uses_shared_root_helper -q`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add scripts/plugin-root.sh scripts/run-mcp.sh tests/test_plugin_layout.py
git commit -m "refactor: centralize plugin root resolution"
```

### Task 2: Make Hooks Host-Neutral

**Files:**
- Modify: `hooks/hooks.json`
- Modify: `hooks/session-start`
- Modify: `scripts/plugin-root.sh`
- Test: `tests/test_plugin_layout.py`

- [ ] **Step 1: Write the failing test**

```python
from pathlib import Path


def test_hooks_do_not_hardcode_claude_root() -> None:
    hooks_json = Path("hooks/hooks.json").read_text(encoding="utf-8")
    assert "CLAUDE_PLUGIN_ROOT" not in hooks_json
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run python -m pytest tests/test_plugin_layout.py::test_hooks_do_not_hardcode_claude_root -q`
Expected: FAIL because `hooks/hooks.json` still hardcodes `CLAUDE_PLUGIN_ROOT`

- [ ] **Step 3: Write minimal implementation**

```json
{
  "hooks": {
    "SessionStart": [
      {
        "matcher": "",
        "hooks": [
          {
            "type": "command",
            "command": "\"${CODEX_PLUGIN_ROOT:-${CLAUDE_PLUGIN_ROOT:-${OPENCLAW_PLUGIN_ROOT:-$PWD}}}/hooks/session-start\"",
            "timeout": 10000
          }
        ]
      }
    ]
  }
}
```

Update `hooks/session-start` to resolve its root through `scripts/plugin-root.sh` before doing any repo-relative work, so both the MCP launcher and hook path share one root-resolution rule.

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run python -m pytest tests/test_plugin_layout.py::test_hooks_do_not_hardcode_claude_root -q`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add hooks/hooks.json hooks/session-start scripts/plugin-root.sh tests/test_plugin_layout.py
git commit -m "fix: make hooks host-neutral"
```

### Task 3: Tighten Plugin Manifests And Installation Docs

**Files:**
- Modify: `.codex-plugin/plugin.json`
- Modify: `.claude-plugin/plugin.json`
- Add: `docs/plugin-installation.md`
- Modify: `README.md`
- Test: `tests/test_plugin_layout.py`

- [ ] **Step 1: Write the failing test**

```python
import json
from pathlib import Path


def test_plugin_docs_and_manifests_describe_root_as_plugin() -> None:
    codex_manifest = json.loads(Path(".codex-plugin/plugin.json").read_text(encoding="utf-8"))
    readme = Path("README.md").read_text(encoding="utf-8")
    assert codex_manifest["name"] == "paper-distill"
    assert "repository root as the plugin root" in readme
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run python -m pytest tests/test_plugin_layout.py::test_plugin_docs_and_manifests_describe_root_as_plugin -q`
Expected: FAIL because the new wording and installation doc do not exist yet

- [ ] **Step 3: Write minimal implementation**

```markdown
# Plugin Installation

Paper Distill uses the repository root as the plugin root.

- Codex: register this checkout as a local plugin
- Claude: point Claude at this checkout's `.claude-plugin/plugin.json`
- OpenClaw: use the same checkout and shared `.mcp.json` runtime

Uninstall means removing the host registration, not deleting the repository.
```

Update `README.md` to link the installation doc and add one short section explaining root-as-plugin semantics. Only add manifest changes that clarify host role; do not duplicate Codex interface metadata into the Claude manifest.

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run python -m pytest tests/test_plugin_layout.py::test_plugin_docs_and_manifests_describe_root_as_plugin -q`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add .codex-plugin/plugin.json .claude-plugin/plugin.json docs/plugin-installation.md README.md tests/test_plugin_layout.py
git commit -m "docs: describe root-as-plugin installation"
```

### Task 4: Add Cross-Host Regression Coverage And Final Verification

**Files:**
- Create: `tests/test_plugin_layout.py`
- Modify: `docs/testing.md`

- [ ] **Step 1: Write the failing test**

```python
import json
from pathlib import Path


def test_mcp_root_resolution_mentions_all_supported_hosts() -> None:
    mcp = json.loads(Path(".mcp.json").read_text(encoding="utf-8"))
    command = mcp["mcpServers"]["paper-distill"]["args"][1]
    assert "CLAUDE_PLUGIN_ROOT" in command
    assert "CODEX_PLUGIN_ROOT" in command
    assert "OPENCLAW_PLUGIN_ROOT" in command
```

- [ ] **Step 2: Run test to verify it fails if coverage is incomplete**

Run: `uv run python -m pytest tests/test_plugin_layout.py -q`
Expected: FAIL until all new plugin-layout checks and docs are in place

- [ ] **Step 3: Finish the test module and testing docs**

```python
def test_codex_plugin_manifest_points_at_repo_assets() -> None:
    codex = json.loads(Path(".codex-plugin/plugin.json").read_text(encoding="utf-8"))
    assert codex["skills"] == "./skills/"
    assert codex["hooks"] == "./hooks/hooks.json"
    assert codex["mcpServers"] == "./.mcp.json"
```

Update `docs/testing.md` with one focused verification command for cross-host plugin layout checks.

- [ ] **Step 4: Run the full verification set**

Run: `uv run python -m pytest tests/test_plugin_layout.py tests/test_v3_commands.py tests/test_skill_inventory.py tests/test_no_retired_names.py -q`
Expected: PASS

Run: `uv run python -m pytest -q`
Expected: PASS

Run: `uv run python -m compileall -q server tests`
Expected: exit code 0

- [ ] **Step 5: Commit**

```bash
git add tests/test_plugin_layout.py docs/testing.md
git commit -m "test: cover cross-host plugin layout"
```
