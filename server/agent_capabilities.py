"""Agent-facing Paper Distill capability inventory."""
from __future__ import annotations

from typing import Any


AGENT_CAPABILITY_INDEX: dict[str, list[dict[str, str]]] = {
    "skills": [
        {
            "name": "paper-intake",
            "use_when": "discovering papers, approving inbox candidates, or ingesting arXiv evidence",
        },
        {
            "name": "paper-distillation",
            "use_when": "turning captured raw evidence into canonical paper pages",
        },
        {
            "name": "knowledge-workbench",
            "use_when": "querying the vault, maintaining concepts, writing canonical assets, or linting",
        },
        {
            "name": "idea-workbench",
            "use_when": "creating or curating ideas and conversation insights",
        },
        {
            "name": "qmd-reference",
            "use_when": "checking QMD CLI syntax, collections, contexts, or index refresh commands",
        },
    ],
    "commands": [
        {"name": "/discover", "use_when": "find new papers", "backing": "discover_papers"},
        {"name": "/approve", "use_when": "accept inbox candidates", "backing": "approve_papers"},
        {"name": "/ingest", "use_when": "capture approved or resolved arXiv papers", "backing": "ingest_and_read"},
        {"name": "/lint", "use_when": "audit vault structure and weak links", "backing": "lint_vault"},
        {"name": "/status", "use_when": "summarize vault health", "backing": "lint_vault plus agent-side counts"},
    ],
    "mcp_tools": [
        {"name": "discover_papers", "use_when": "find new papers and write inbox stubs"},
        {"name": "approve_papers", "use_when": "mark selected inbox stubs approved from chat"},
        {"name": "ingest_and_read", "use_when": "capture approved notes or resolved arXiv identities"},
        {"name": "distill_paper", "use_when": "distill one captured raw evidence note into a canonical paper page"},
        {"name": "distill_papers", "use_when": "distill several captured papers sequentially"},
        {"name": "upsert_wiki_page", "use_when": "write canonical paper, concept, idea, or conversation pages"},
        {"name": "check_concept_alias", "use_when": "resolve uncertain concept surfaces before linking"},
        {"name": "merge_concept", "use_when": "merge concept aliases and rewrite wikilinks"},
        {"name": "lint_vault", "use_when": "report structural and semantic vault issues"},
    ],
    "qmd": [
        {"name": "qmd query", "use_when": "search existing vault content"},
        {"name": "qmd get", "use_when": "read a known page or raw evidence file"},
        {"name": "qmd status", "use_when": "check index and collection readiness"},
        {"name": "qmd update", "use_when": "refresh the index after business writes"},
        {"name": "qmd embed -f", "use_when": "force embeddings when semantic retrieval must be current"},
    ],
    "routing": [
        {"name": "Find new papers", "use_when": "call discover_papers, not qmd query."},
        {"name": "Query existing vault content", "use_when": "use qmd query or qmd get."},
        {"name": "Ingest known papers", "use_when": "resolve natural references to arXiv identities, then call ingest_and_read."},
        {"name": "Distill captured evidence", "use_when": "use distill_paper or distill_papers."},
        {"name": "Write canonical pages", "use_when": "use upsert_wiki_page."},
        {"name": "Flag weak decorative concept links", "use_when": "lint_vault reports decorative_concept_link."},
    ],
}


def expected_mcp_tool_names() -> set[str]:
    return {item["name"] for item in AGENT_CAPABILITY_INDEX["mcp_tools"]}


def _render_items(title: str, items: list[dict[str, str]]) -> list[str]:
    lines = [f"{title}:"]
    for item in items:
        backing = item.get("backing")
        suffix = f" -> {backing}" if backing else ""
        lines.append(f"- {item['name']}{suffix}: {item['use_when']}")
    return lines


def render_session_context(index: dict[str, Any] | None = None) -> str:
    capability_index = index or AGENT_CAPABILITY_INDEX
    lines = [
        "You have Paper Distill v3 installed.",
        "",
        "Agent-facing capability index:",
    ]
    lines.extend(_render_items("Skills", capability_index["skills"]))
    lines.extend(_render_items("Slash commands", capability_index["commands"]))
    lines.extend(_render_items("MCP tools", capability_index["mcp_tools"]))
    lines.extend(_render_items("QMD CLI", capability_index["qmd"]))
    lines.append("Routing rules:")
    for item in capability_index["routing"]:
        lines.append(f"- {item['name']}: {item['use_when']}")
    lines.append("")
    lines.append("QMD remains the read/index surface; business MCP owns discovery, ingest, deterministic writes, distillation, and linting.")
    return "\n".join(lines)


def main() -> None:
    print(render_session_context())


if __name__ == "__main__":
    main()
