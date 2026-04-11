from __future__ import annotations

from fastmcp import FastMCP

from server.server_runtime import (
    _MCP_TOOL_SURFACE,
    bootstrap_vault,
    fetch_pdf_text,
    query_vault,
    resolve_metadata,
    score_papers,
    search_papers,
    update_learned_preferences,
    zotero_add,
    zotero_search,
)


def register_library_tools(mcp: FastMCP) -> None:
    mcp.tool()(search_papers)
    mcp.tool()(resolve_metadata)
    mcp.tool()(zotero_add)
    mcp.tool()(zotero_search)
    mcp.tool()(fetch_pdf_text)
    mcp.tool()(score_papers)
    mcp.tool(name=_MCP_TOOL_SURFACE["query_library"])(query_vault)
    mcp.tool(name=_MCP_TOOL_SURFACE["bootstrap_library"])(bootstrap_vault)
    mcp.tool()(update_learned_preferences)
