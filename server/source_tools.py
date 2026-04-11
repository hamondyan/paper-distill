from __future__ import annotations

from fastmcp import FastMCP

from server.server_runtime import (
    _MCP_TOOL_SURFACE,
    discover_papers,
    source_ingest,
)


def register_source_tools(mcp: FastMCP) -> None:
    mcp.tool(name=_MCP_TOOL_SURFACE["source_discover"])(discover_papers)
    mcp.tool(name=_MCP_TOOL_SURFACE["source_ingest"])(source_ingest)
