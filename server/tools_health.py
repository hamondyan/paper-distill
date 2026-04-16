"""Health v3 MCP tools."""
from __future__ import annotations

from typing import Any

from fastmcp import FastMCP

from server.v3_health import lint_vault_v3


async def lint_vault() -> dict[str, Any]:
    return lint_vault_v3()


def register_health_tools(mcp: FastMCP) -> None:
    mcp.tool(name="lint_vault")(lint_vault)
