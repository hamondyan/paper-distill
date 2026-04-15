"""Idea MCP tools — research gap analysis and idea generation.

Registers:
    idea-analyze — one-shot analysis returning gaps, tension signals,
                   and trigger candidates
"""
from __future__ import annotations

from typing import Any

from fastmcp import FastMCP

from server.server_runtime import (
    analyze_knowledge_graph as _idea_discover,
    query_tension_signals as _tension_signals,
    query_trigger_candidates as _trigger_candidates,
)


# ------------------------------------------------------------------
# Tool 11: idea-analyze
# ------------------------------------------------------------------

async def idea_analyze(
    user_topics: list[str] | None = None,
    min_occurrence: int = 2,
    topic: str | None = None,
) -> dict[str, Any]:
    """Analyze the knowledge vault for research gaps and idea opportunities.

    Returns a combined analysis in a single call:

    - **gaps**: graph-level analysis — methodology mismatches, combination
      opportunities, recurring problems, scaling questions.
    - **tension_signals**: IR-level tensions — recurring limitations
      (appearing in ≥ min_occurrence papers), assumptions, open question
      clusters, negative results.
    - **trigger_candidates**: high-signal patterns — contradiction
      candidates, limitation spikes, cross-cluster bridges, benchmark
      evaluation splits.

    After receiving results, read 2-3 referenced papers for each
    promising gap before drafting idea notes.

    Args:
        user_topics: Research topics for mismatch analysis (reads from
                     settings.json if omitted).
        min_occurrence: Minimum papers a limitation must appear in for
                        tension_signals (default 2).
        topic: Optional topic filter for tension signals.
    """
    # 1. Graph analysis → gaps + runtime context
    gaps_result = await _idea_discover(user_topics=user_topics)

    # 2. Tension signals from resolved IRs
    tensions_result = await _tension_signals(
        min_occurrence=min_occurrence,
        topic=topic,
    )

    # 3. Trigger candidates (narrowed view)
    triggers_result = await _trigger_candidates(user_topics=user_topics)

    # Combine into a single response
    return {
        "gaps": {
            k: v for k, v in gaps_result.items()
            if k not in ("runtime_context", "local_memory_evidence", "error")
        },
        "tension_signals": {
            k: v for k, v in tensions_result.items()
            if k != "error"
        },
        "trigger_candidates": triggers_result.get("trigger_candidates", {}),
        "runtime_context": gaps_result.get("runtime_context", {}),
        "local_memory_evidence": gaps_result.get("local_memory_evidence", []),
        "paper_count": gaps_result.get("paper_count", 0),
        "concept_count": gaps_result.get("concept_count", 0),
        "error": gaps_result.get("error", "") or tensions_result.get("error", ""),
    }


# ------------------------------------------------------------------
# Registration
# ------------------------------------------------------------------

def register_idea_tools(mcp: FastMCP) -> None:
    mcp.tool(name="idea-analyze")(idea_analyze)
