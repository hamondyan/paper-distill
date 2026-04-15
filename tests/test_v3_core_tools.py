from __future__ import annotations

import asyncio

from server.server import mcp
from server import tools_core


def test_mcp_lists_v3_core_read_surface_names() -> None:
    tools = asyncio.run(mcp.list_tools())
    names = {tool.name for tool in tools}

    assert "kb_search" in names
    assert "kb_get" in names
    assert "status" in names


def test_kb_search_returns_not_ready_from_delegate(monkeypatch) -> None:
    monkeypatch.setattr(
        tools_core,
        "_kb_search",
        lambda query, scope="canon": {
            "status": "not_ready",
            "error": "qmd binary not found",
            "query": query,
            "scope": scope,
        },
    )

    result = asyncio.run(
        mcp.call_tool("kb_search", {"query": "graph attention", "scope": "canon"})
    )

    assert result.structured_content == {
        "status": "not_ready",
        "error": "qmd binary not found",
        "query": "graph attention",
        "scope": "canon",
    }


def test_kb_get_returns_current_file_truth_from_delegate(monkeypatch) -> None:
    monkeypatch.setattr(
        tools_core,
        "_kb_get",
        lambda id_or_path: {
            "status": "ok",
            "path": "wiki/papers/attention-is-all-you-need.md",
            "body": "# Attention Is All You Need\n",
        },
    )

    result = asyncio.run(
        mcp.call_tool("kb_get", {"id_or_path": "attention-is-all-you-need"})
    )

    assert result.structured_content == {
        "status": "ok",
        "path": "wiki/papers/attention-is-all-you-need.md",
        "body": "# Attention Is All You Need\n",
    }
