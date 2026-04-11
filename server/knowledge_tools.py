from __future__ import annotations

from fastmcp import FastMCP

from server.server_runtime import (
    _MCP_TOOL_SURFACE,
    backfill_registry,
    commit_compile_result,
    enqueue_maintenance_task,
    execute_maintenance_task,
    export_db_state,
    get_compile_state,
    get_maintenance_queue,
    lint_vault,
    list_concepts_tool,
    merge_concepts_tool,
    reconcile_maintenance,
    register_concept_tool,
    resolve_compile_ir,
    resolve_concept_tool,
    resolve_maintenance_task,
    upsert_wiki_article,
    vault_stats,
    write_compile_ir,
)


def register_knowledge_tools(mcp: FastMCP) -> None:
    mcp.tool(name=_MCP_TOOL_SURFACE["wiki_lint"])(lint_vault)
    mcp.tool(name=_MCP_TOOL_SURFACE["library_stats"])(vault_stats)
    mcp.tool()(upsert_wiki_article)
    mcp.tool()(register_concept_tool)
    mcp.tool()(resolve_concept_tool)
    mcp.tool()(merge_concepts_tool)
    mcp.tool()(list_concepts_tool)
    mcp.tool()(reconcile_maintenance)
    mcp.tool()(get_maintenance_queue)
    mcp.tool()(resolve_maintenance_task)
    mcp.tool()(export_db_state)
    mcp.tool()(backfill_registry)
    mcp.tool(name=_MCP_TOOL_SURFACE["paper_distill_extract"])(write_compile_ir)
    mcp.tool(name=_MCP_TOOL_SURFACE["knowledge_compile_resolve"])(resolve_compile_ir)
    mcp.tool(name=_MCP_TOOL_SURFACE["knowledge_compile_publish"])(commit_compile_result)
    mcp.tool(name=_MCP_TOOL_SURFACE["knowledge_compile_status"])(get_compile_state)
    mcp.tool()(execute_maintenance_task)
    mcp.tool()(enqueue_maintenance_task)
