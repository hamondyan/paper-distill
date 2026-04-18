from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]


def test_mcp_launcher_uses_shared_root_helper() -> None:
    launcher = Path("scripts/run-mcp.sh").read_text(encoding="utf-8")
    assert "plugin-root.sh" in launcher
    assert 'uv --directory "${REPO_ROOT}" run paper-distill-server' in launcher


def test_hooks_json_does_not_hardcode_claude_plugin_root() -> None:
    hooks_json = json.loads((REPO_ROOT / "hooks" / "hooks.json").read_text(encoding="utf-8"))
    command = hooks_json["hooks"]["SessionStart"][0]["hooks"][0]["command"]
    assert "/bin/bash -lc" in command
    assert "scripts/plugin-root.sh" in command
    assert "hooks/session-start" in command
    assert "CLAUDE_PLUGIN_ROOT" not in command


def test_session_start_resolves_root_via_shared_helper() -> None:
    session_start = (REPO_ROOT / "hooks" / "session-start").read_text(encoding="utf-8")
    assert "plugin-root.sh" in session_start


def test_plugin_root_helper_honors_precedence_and_repo_fallback() -> None:
    script = REPO_ROOT / "scripts" / "plugin-root.sh"
    base_env = os.environ.copy()
    for key in ("CLAUDE_PLUGIN_ROOT", "CODEX_PLUGIN_ROOT", "OPENCLAW_PLUGIN_ROOT"):
        base_env.pop(key, None)

    def run_with_env(**env: str) -> str:
        proc = subprocess.run(
            ["bash", str(script)],
            check=True,
            cwd=REPO_ROOT,
            env={**base_env, **env},
            text=True,
            capture_output=True,
        )
        return proc.stdout.strip()

    assert run_with_env() == str(REPO_ROOT)
    assert run_with_env(OPENCLAW_PLUGIN_ROOT="/tmp/openclaw") == "/tmp/openclaw"
    assert run_with_env(CODEX_PLUGIN_ROOT="/tmp/codex", OPENCLAW_PLUGIN_ROOT="/tmp/openclaw") == "/tmp/codex"
    assert run_with_env(
        CLAUDE_PLUGIN_ROOT="/tmp/claude",
        CODEX_PLUGIN_ROOT="/tmp/codex",
        OPENCLAW_PLUGIN_ROOT="/tmp/openclaw",
    ) == "/tmp/claude"
