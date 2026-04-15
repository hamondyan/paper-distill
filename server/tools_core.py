"""Core MCP tools — always-visible, cross-cutting utilities.

Registers:
    query-library   — unified read-only vault query (sections, stats, lint,
                       compile_status, concepts)
    update-preferences — update user's learned preferences
"""
from __future__ import annotations

from typing import Any

from fastmcp import FastMCP

from server.server_runtime import (
    get_vault_path,
    query_vault as _query_vault,
    lint_vault as _lint_vault,
    vault_stats as _vault_stats,
    get_compile_state as _get_compile_state,
    list_concepts_tool as _list_concepts,
    update_learned_preferences as _update_prefs,
)


# ------------------------------------------------------------------
# Tool 1: query-library (unified read-only query)
# ------------------------------------------------------------------

async def query_library(
    view: str = "sections",
    section: str = "all",
    topic: str | None = None,
    status: str | None = None,
    uncompiled_only: bool = False,
    detail: str = "compact",
    limit: int | None = None,
    sort_by: str = "updated_at",
    days_back: int | None = None,
    page_id: str | None = None,
    page_type: str = "paper",
    concept_type: str | None = None,
    min_paper_count: int = 0,
) -> dict[str, Any]:
    """Query the Paper Distill library — the single read-only entry point.

    Use the ``view`` parameter to select what to query:

    - ``sections`` (default): browse library items by section (inbox,
      sources, papers, concepts, methods, topics, or all).
    - ``stats``: vault-wide statistics (paper counts, compilation rate,
      per-topic breakdown, last activity).
    - ``lint``: structural health checks (orphaned articles, broken
      backlinks, missing frontmatter, stale indexes, uncompiled papers).
    - ``compile_status``: compile state for a specific page (version,
      hash, compiled_at).  Requires ``page_id``.
    - ``concepts``: list concepts from the canonical registry, optionally
      filtered by type and minimum paper count.

    Args:
        view: Query view — "sections" | "stats" | "lint" |
              "compile_status" | "concepts".
        section: For view=sections: "inbox", "source_evidence", "sources",
                 "papers", "concepts", "methods", "topics", or "all".
        topic: Filter by topic tag (optional).
        status: Filter inbox notes by status (optional).
        uncompiled_only: If True, only return uncompiled source evidence.
        detail: "compact" (strips heavy fields) or "full".
        limit: Max items per section.
        sort_by: Sort field — "updated_at" or "_mtime".
        days_back: Only items modified within N days.
        page_id: For view=compile_status: page identifier (citekey/slug).
        page_type: For view=compile_status: "paper" | "concept" etc.
        concept_type: For view=concepts: "concept" | "method" | "topic".
        min_paper_count: For view=concepts: minimum paper count filter.
    """
    if view == "stats":
        return await _vault_stats()
    if view == "lint":
        return await _lint_vault()
    if view == "compile_status":
        if not page_id:
            return {"error": "page_id is required for view='compile_status'"}
        return await _get_compile_state(page_id, page_type)
    if view == "concepts":
        return {"concepts": await _list_concepts(concept_type, min_paper_count)}
    # default: sections
    return await _query_vault(
        section=section,
        topic=topic,
        uncompiled_only=uncompiled_only,
        status=status,
        detail=detail,
        limit=limit,
        sort_by=sort_by,
        days_back=days_back,
    )


# ------------------------------------------------------------------
# Tool 2: update-preferences
# ------------------------------------------------------------------

async def update_preferences(
    accepted_keywords: list[str] | None = None,
    rejected_keywords: list[str] | None = None,
    preferred_venues: list[str] | None = None,
) -> dict[str, Any]:
    """Update the user's learned preferences in settings.json.

    Atomically appends new items to existing lists without overwriting.

    Args:
        accepted_keywords: Keywords to add to accepted list.
        rejected_keywords: Keywords to add to rejected list.
        preferred_venues: Venues to add to preferred list.
    """
    return await _update_prefs(
        accepted_keywords=accepted_keywords,
        rejected_keywords=rejected_keywords,
        preferred_venues=preferred_venues,
    )


# ------------------------------------------------------------------
# Registration
# ------------------------------------------------------------------

def register_core_tools(mcp: FastMCP) -> None:
    mcp.tool(name="query-library")(query_library)
    mcp.tool(name="update-preferences")(update_preferences)
