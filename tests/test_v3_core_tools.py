from __future__ import annotations

import asyncio
from pathlib import Path
from unittest.mock import Mock

from server import qmd_runtime
from server import tools_core
from server.server import mcp


def test_mcp_lists_v3_core_read_surface_names() -> None:
    tools = asyncio.run(mcp.list_tools())
    names = {tool.name for tool in tools}

    assert "kb_search" in names
    assert "kb_get" in names
    assert "status" in names


def test_kb_search_returns_not_ready_when_qmd_is_missing(monkeypatch, tmp_path: Path) -> None:
    ensured: list[Path] = []

    monkeypatch.setattr(tools_core, "get_vault_path", lambda: str(tmp_path))
    monkeypatch.setattr(
        tools_core,
        "ensure_v3_layout",
        lambda vault_path: ensured.append(vault_path) or {"created": []},
    )

    def raise_missing(*_args, **_kwargs):
        raise FileNotFoundError("qmd")

    monkeypatch.setattr(qmd_runtime.subprocess, "run", raise_missing)

    result = asyncio.run(tools_core.kb_search(query="graph attention", scope="canon"))

    assert ensured == [tmp_path]
    assert result == {
        "status": "not_ready",
        "error": "qmd binary not found",
    }


def test_kb_get_returns_current_file_truth_from_qmd_runtime(
    monkeypatch, tmp_path: Path
) -> None:
    vault_path = tmp_path
    doc = vault_path / "wiki" / "papers" / "attention-is-all-you-need.md"
    doc.parent.mkdir(parents=True)
    doc.write_text("# Attention Is All You Need\n", encoding="utf-8")

    ensured: list[Path] = []

    monkeypatch.setattr(tools_core, "get_vault_path", lambda: str(vault_path))
    monkeypatch.setattr(
        tools_core,
        "ensure_v3_layout",
        lambda path: ensured.append(path) or {"created": []},
    )

    def fake_run(args, **_kwargs):
        if args == ["qmd", "get", str(doc)]:
            return Mock(stdout="# Attention Is All You Need\n")
        raise AssertionError(f"unexpected qmd command: {args}")

    monkeypatch.setattr(qmd_runtime.subprocess, "run", fake_run)

    result = asyncio.run(tools_core.kb_get("wiki/papers/attention-is-all-you-need.md"))

    assert ensured == [vault_path]
    assert result == {
        "status": "ok",
        "path": str(doc),
        "body": "# Attention Is All You Need\n",
    }


def test_status_attempts_qmd_bootstrap_before_reporting_readiness(
    monkeypatch, tmp_path: Path
) -> None:
    calls: list[tuple[str, object]] = []

    monkeypatch.setattr(tools_core, "get_vault_path", lambda: str(tmp_path))

    def fake_ensure_v3_layout(vault_path: Path) -> dict[str, object]:
        calls.append(("layout", vault_path))
        return {"created": ["wiki/papers"]}

    def fake_ensure_qmd_ready(vault_path: Path) -> dict[str, object]:
        calls.append(("qmd_bootstrap", vault_path))
        raise FileNotFoundError("qmd")

    def fake_qmd_ready_report(vault_path: Path) -> dict[str, object]:
        calls.append(("qmd_report", vault_path))
        return {"status": "not_ready", "reason": "qmd binary not found"}

    monkeypatch.setattr(tools_core, "ensure_v3_layout", fake_ensure_v3_layout)
    monkeypatch.setattr(tools_core, "ensure_qmd_ready", fake_ensure_qmd_ready)
    monkeypatch.setattr(tools_core, "qmd_ready_report", fake_qmd_ready_report)

    result = asyncio.run(tools_core.status())

    assert calls == [
        ("layout", tmp_path),
        ("qmd_bootstrap", tmp_path),
        ("qmd_report", tmp_path),
    ]
    assert result == {
        "layout": {"created": ["wiki/papers"]},
        "qmd": {"status": "not_ready", "reason": "qmd binary not found"},
    }
