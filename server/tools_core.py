"""Core v3 MCP tools.

Registers:
    kb_search          - search the qmd-backed knowledge base
    kb_get             - fetch the current truth for a document
    status             - report v3 vault layout and qmd readiness
    update-preferences - update user's learned preferences
"""
from __future__ import annotations

from typing import Any

from fastmcp import FastMCP

from server.server_runtime import (
    kb_get as _kb_get,
    kb_search as _kb_search,
    update_learned_preferences as _update_prefs,
    v3_status as _v3_status,
)


async def kb_search(query: str, scope: str = "canon") -> dict[str, Any]:
    """Search the qmd-backed knowledge base."""
    return _kb_search(query=query, scope=scope)


async def kb_get(id_or_path: str) -> dict[str, Any]:
    """Fetch the current file truth by stable ID or vault-relative path."""
    return _kb_get(id_or_path=id_or_path)


async def status() -> dict[str, Any]:
    """Report v3 vault layout and qmd readiness."""
    return _v3_status()


async def update_preferences(
    accepted_keywords: list[str] | None = None,
    rejected_keywords: list[str] | None = None,
    preferred_venues: list[str] | None = None,
) -> dict[str, Any]:
    """Update the user's learned preferences in settings.json."""
    return await _update_prefs(
        accepted_keywords=accepted_keywords,
        rejected_keywords=rejected_keywords,
        preferred_venues=preferred_venues,
    )


def register_core_tools(mcp: FastMCP) -> None:
    mcp.tool(name="kb_search")(kb_search)
    mcp.tool(name="kb_get")(kb_get)
    mcp.tool(name="status")(status)
