"""Health MCP tools — vault structural health and statistics.

Registers:
    lint_vault   — v3 health checks
    vault-health — combined lint + stats report
"""
from __future__ import annotations

from typing import Any

from fastmcp import FastMCP

from server.server_runtime import (
    lint_vault_v3 as _lint_v3,
    vault_stats as _vault_stats,
)


# ------------------------------------------------------------------
# Tool 11: lint_vault
# ------------------------------------------------------------------

async def lint_vault() -> dict[str, Any]:
    """Run v3 vault health checks without mutating the library."""
    return await _lint_v3()


# ------------------------------------------------------------------
# Tool 12: vault-health
# ------------------------------------------------------------------

async def vault_health() -> dict[str, Any]:
    """Return a combined vault health report (lint issues + statistics).

    Runs both structural health checks and statistics gathering in one
    call.  Equivalent to calling ``query-library(view="lint")`` and
    ``query-library(view="stats")`` together.

    Returns:
        Dict with two top-level keys:
        - ``lint``: orphaned articles, broken backlinks, missing
          frontmatter, stale indexes, uncompiled papers, missing
          concept stubs.
        - ``stats``: paper counts per stage, compilation rate,
          wiki article counts, per-topic breakdowns, last activity.
    """
    lint_result = await _lint_v3()
    stats_result = await _vault_stats()

    return {
        "lint": lint_result,
        "stats": stats_result,
    }


# ------------------------------------------------------------------
# Registration
# ------------------------------------------------------------------

def register_health_tools(mcp: FastMCP) -> None:
    mcp.tool(name="lint_vault")(lint_vault)
