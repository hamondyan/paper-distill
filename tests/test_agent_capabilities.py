from __future__ import annotations

from server.agent_capabilities import (
    AGENT_CAPABILITY_INDEX,
    expected_mcp_tool_names,
    render_session_context,
)


def test_capability_index_lists_first_hop_surfaces() -> None:
    assert [item["name"] for item in AGENT_CAPABILITY_INDEX["skills"]] == [
        "paper-intake",
        "paper-distillation",
        "knowledge-workbench",
        "idea-workbench",
        "qmd-reference",
    ]
    assert "/discover" in {item["name"] for item in AGENT_CAPABILITY_INDEX["commands"]}
    assert "distill_paper" in expected_mcp_tool_names()
    assert "distill_papers" in expected_mcp_tool_names()
    assert "qmd query" in {item["name"] for item in AGENT_CAPABILITY_INDEX["qmd"]}


def test_render_session_context_contains_routing_rules() -> None:
    context = render_session_context()

    assert "Agent-facing capability index" in context
    assert "Find new papers: call discover_papers for chat-only candidates, not qmd query." in context
    assert "Query existing vault content: use qmd query or qmd get." in context
    assert "Distill captured evidence: use distill_paper or distill_papers." in context
    assert "Write canonical pages: use upsert_wiki_page." in context
    assert "Flag weak decorative concept links: lint_vault reports decorative_concept_link." in context
    assert "/approve" not in context
    assert "approve_papers" not in context
