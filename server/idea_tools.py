from __future__ import annotations

from fastmcp import FastMCP

from server.server_runtime import (
    _MCP_TOOL_SURFACE,
    analyze_knowledge_graph,
    query_tension_signals,
    query_trigger_candidates,
)


def register_idea_tools(mcp: FastMCP) -> None:
    mcp.tool(name=_MCP_TOOL_SURFACE["idea_discover"])(analyze_knowledge_graph)
    mcp.tool(name=_MCP_TOOL_SURFACE["idea_tension_signals"])(query_tension_signals)
    mcp.tool(name=_MCP_TOOL_SURFACE["idea_trigger_candidates"])(query_trigger_candidates)
