from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path
from tempfile import TemporaryDirectory


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


def test_hooks_command_runs_through_bash_with_spaced_root() -> None:
    hooks_json = json.loads((REPO_ROOT / "hooks" / "hooks.json").read_text(encoding="utf-8"))
    command = hooks_json["hooks"]["SessionStart"][0]["hooks"][0]["command"]

    with TemporaryDirectory(prefix="paper distill ") as temp_dir:
        temp_root = Path(temp_dir)
        spaced_root = temp_root / "plugin root"
        spaced_root.mkdir()
        repo_link = spaced_root / "paper-distill"
        repo_link.symlink_to(REPO_ROOT, target_is_directory=True)

        proc = subprocess.run(
            ["bash", "-lc", command],
            cwd=repo_link,
            env={
                **os.environ,
                "CODEX_PLUGIN_ROOT": str(repo_link),
                "CLAUDE_PLUGIN_ROOT": "",
                "OPENCLAW_PLUGIN_ROOT": "",
            },
            text=True,
            capture_output=True,
            check=True,
        )

    payload = json.loads(proc.stdout)
    assert "additionalContext" in payload
    assert "Paper Distill v3 installed" in payload["additionalContext"]


def test_hooks_command_uses_claude_override_branch() -> None:
    hooks_json = json.loads((REPO_ROOT / "hooks" / "hooks.json").read_text(encoding="utf-8"))
    command = hooks_json["hooks"]["SessionStart"][0]["hooks"][0]["command"]

    with TemporaryDirectory(prefix="paper distill ") as temp_dir:
        temp_root = Path(temp_dir)

        def write_fake_helper(root: Path, resolved_root: str) -> None:
            helper_dir = root / "scripts"
            helper_dir.mkdir(parents=True)
            helper = helper_dir / "plugin-root.sh"
            helper.write_text(
                f"#!/usr/bin/env bash\nprintf '%s\\n' '{resolved_root}'\n",
                encoding="utf-8",
            )
            helper.chmod(0o755)

        fake_cwd = temp_root / "cwd helper"
        fake_cwd.mkdir()
        write_fake_helper(fake_cwd, "/definitely/not/the/cwd/root")

        fake_codex_root = temp_root / "codex plugin root"
        write_fake_helper(fake_codex_root, "/definitely/not/the/codex/root")

        fake_openclaw_root = temp_root / "openclaw plugin root"
        write_fake_helper(fake_openclaw_root, "/definitely/not/the/openclaw/root")

        spaced_root = temp_root / "claude plugin root"
        spaced_root.mkdir()
        repo_link = spaced_root / "paper-distill"
        repo_link.symlink_to(REPO_ROOT, target_is_directory=True)

        proc = subprocess.run(
            ["bash", "-lc", command],
            cwd=fake_cwd,
            env={
                **os.environ,
                "CLAUDE_PLUGIN_ROOT": str(repo_link),
                "CODEX_PLUGIN_ROOT": str(fake_codex_root),
                "OPENCLAW_PLUGIN_ROOT": str(fake_openclaw_root),
            },
            text=True,
            capture_output=True,
            check=True,
        )

    payload = json.loads(proc.stdout)
    assert payload["hookSpecificOutput"]["hookEventName"] == "SessionStart"
    assert "Paper Distill v3 installed" in payload["hookSpecificOutput"]["additionalContext"]


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


def test_plugin_docs_and_manifests_describe_root_as_plugin() -> None:
    codex_manifest = json.loads((REPO_ROOT / ".codex-plugin" / "plugin.json").read_text(encoding="utf-8"))
    claude_manifest = json.loads((REPO_ROOT / ".claude-plugin" / "plugin.json").read_text(encoding="utf-8"))
    readme = (REPO_ROOT / "README.md").read_text(encoding="utf-8")
    docs_readme = (REPO_ROOT / "docs" / "README.md").read_text(encoding="utf-8")
    installation = (REPO_ROOT / "docs" / "plugin-installation.md").read_text(encoding="utf-8")

    assert "repository root as the plugin root" in readme
    assert "[Plugin Installation](docs/plugin-installation.md)" in readme
    assert "[Plugin Installation](plugin-installation.md)" in docs_readme
    assert "registering this checkout as a local plugin root" in installation
    assert "Codex local plugin manifest" in codex_manifest["description"]
    assert "Claude compatibility manifest" in claude_manifest["description"]
