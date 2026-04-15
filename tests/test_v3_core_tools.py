from __future__ import annotations

import asyncio
from pathlib import Path
from unittest.mock import Mock

from server.server import mcp
from server import qmd_runtime, server_runtime


def test_mcp_lists_v3_core_read_surface_names() -> None:
    tools = asyncio.run(mcp.list_tools())
    names = {tool.name for tool in tools}

    assert "kb_search" in names
    assert "kb_get" in names
    assert "status" in names


def test_kb_search_returns_not_ready_when_qmd_is_missing(monkeypatch, tmp_path: Path) -> None:
    ensured: list[Path] = []

    monkeypatch.setattr(server_runtime, "get_vault_path", lambda: str(tmp_path))
    monkeypatch.setattr(
        server_runtime,
        "ensure_v3_layout",
        lambda vault_path: ensured.append(vault_path) or {"created": []},
    )

    def raise_missing(*_args, **_kwargs):
        raise FileNotFoundError("qmd")

    monkeypatch.setattr(qmd_runtime.subprocess, "run", raise_missing)

    result = server_runtime.kb_search(query="graph attention", scope="canon")

    assert ensured == [tmp_path]
    assert result == {
        "status": "not_ready",
        "error": "qmd binary not found",
    }


def test_kb_get_returns_current_file_truth_from_real_runtime_path(
    monkeypatch, tmp_path: Path
) -> None:
    vault_path = tmp_path
    doc = vault_path / "wiki" / "papers" / "attention-is-all-you-need.md"
    doc.parent.mkdir(parents=True)
    doc.write_text("# Attention Is All You Need\n", encoding="utf-8")

    ensured: list[Path] = []

    monkeypatch.setattr(server_runtime, "get_vault_path", lambda: str(vault_path))
    monkeypatch.setattr(
        server_runtime,
        "ensure_v3_layout",
        lambda path: ensured.append(path) or {"created": []},
    )

    def fake_run(args, **_kwargs):
        if args == ["qmd", "get", str(doc)]:
            return Mock(stdout="# Attention Is All You Need\n")
        raise AssertionError(f"unexpected qmd command: {args}")

    monkeypatch.setattr(qmd_runtime.subprocess, "run", fake_run)

    result = server_runtime.kb_get("wiki/papers/attention-is-all-you-need.md")

    assert ensured == [vault_path]
    assert result == {
        "status": "ok",
        "path": str(doc),
        "body": "# Attention Is All You Need\n",
    }
