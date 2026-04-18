"""Intake v3 MCP tools."""
from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Any

from fastmcp import FastMCP

from server.config import ConfigError, get_vault_path
from server.v3_approval import approve_papers_v3
from server.v3_discovery import discover_papers_v3
from server.v3_ingest import ingest_and_read_v3


async def discover_papers(query: str | None = None) -> dict[str, Any]:
    return await discover_papers_v3(query=query)


async def approve_papers(input_value: str) -> dict[str, Any]:
    try:
        vault_path = Path(get_vault_path())
    except ConfigError as exc:
        return {"ok": False, "error": str(exc), "approved": [], "errors": []}
    return await asyncio.to_thread(approve_papers_v3, vault_path, input_value)


async def ingest_and_read(input_value: str) -> dict[str, Any]:
    return await ingest_and_read_v3(input_value=input_value)


def register_intake_tools(mcp: FastMCP) -> None:
    mcp.tool(name="discover_papers")(discover_papers)
    mcp.tool(name="approve_papers")(approve_papers)
    mcp.tool(name="ingest_and_read")(ingest_and_read)
