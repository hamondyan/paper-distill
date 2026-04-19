"""Intake v3 MCP tools."""
from __future__ import annotations

from typing import Any

from fastmcp import FastMCP

from server.v3_discovery import discover_papers_v3
from server.v3_ingest import ingest_and_read_v3


async def discover_papers(query: str | None = None) -> dict[str, Any]:
    return await discover_papers_v3(query=query)


async def ingest_and_read(input_value: str) -> dict[str, Any]:
    return await ingest_and_read_v3(input_value=input_value)


def register_intake_tools(mcp: FastMCP) -> None:
    mcp.tool(name="discover_papers")(discover_papers)
    mcp.tool(name="ingest_and_read")(ingest_and_read)
