"""Health v3 MCP tools."""
from __future__ import annotations

import asyncio
from typing import Any

from fastmcp import FastMCP

from server.v3_health import lint_vault_v3


async def lint_vault() -> dict[str, Any]:
    return await asyncio.to_thread(lint_vault_v3)


def register_health_tools(mcp: FastMCP) -> None:
    mcp.tool(name="lint_vault")(lint_vault)
