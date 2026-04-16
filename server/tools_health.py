"""Health v3 MCP tools."""
from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Any

from fastmcp import FastMCP

from server.config import ConfigError, get_vault_path
from server.v3_health import lint_vault_v3


async def lint_vault() -> dict[str, Any]:
    try:
        vault_path = Path(get_vault_path())
    except ConfigError as exc:
        return {"ok": False, "error": str(exc), "issues": []}
    return await asyncio.to_thread(lint_vault_v3, vault_path)


def register_health_tools(mcp: FastMCP) -> None:
    mcp.tool(name="lint_vault")(lint_vault)
