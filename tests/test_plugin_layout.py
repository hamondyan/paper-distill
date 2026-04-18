from __future__ import annotations

import os
import subprocess
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]


def test_mcp_launcher_uses_shared_root_helper() -> None:
    launcher = Path("scripts/run-mcp.sh").read_text(encoding="utf-8")
    assert "plugin-root.sh" in launcher
    assert 'uv --directory "${REPO_ROOT}" run paper-distill-server' in launcher


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
