from __future__ import annotations

import asyncio
from pathlib import Path

from server.server import mcp


EXPECTED_COMMANDS = {"discover", "inbox", "ingest", "search", "get", "lint", "status"}


def test_command_inventory_matches_v3_surface() -> None:
    names = {path.stem for path in Path("commands").glob("*.md")}
    assert names == EXPECTED_COMMANDS


def test_public_command_docs_point_to_v3_tools() -> None:
    get_doc = Path("commands/get.md").read_text(encoding="utf-8")
    search_doc = Path("commands/search.md").read_text(encoding="utf-8")
    status_doc = Path("commands/status.md").read_text(encoding="utf-8")

    assert "kb_get" in get_doc
    assert "kb_search" in search_doc
    assert "not_ready" in search_doc
    assert "qmd" in status_doc
    assert "readiness" in status_doc
    assert "bootstrap" in status_doc


def test_public_docs_describe_v3_qmd_cutover() -> None:
    readme = Path("README.md").read_text(encoding="utf-8")
    installation = Path("docs/installation.md").read_text(encoding="utf-8")
    architecture = Path("docs/architecture.md").read_text(encoding="utf-8")
    commands = Path("docs/commands.md").read_text(encoding="utf-8")
    testing = Path("docs/testing.md").read_text(encoding="utf-8")

    assert "`qmd` is a hard dependency in v3.0" in readme
    assert "discover -> approve -> ingest -> search/get -> lint -> status" in readme
    assert "Run `/status` first" in installation
    assert "qmd collection add <vault>/wiki/papers --name canon-papers" in installation
    assert "qmd collection add <vault>/wiki/concepts --name canon-concepts" in installation
    assert (
        "qmd collection add <vault>/insights/conversations --name insights-conversations"
        in installation
    )
    assert "qmd collection add <vault>/insights/ideas --name insights-ideas" in installation
    assert "qmd collection add <vault>/raw/evidence --name raw-evidence" in installation
    assert 'qmd context add qmd://canon-papers "Canonical distilled papers"' in installation
    assert 'qmd context add qmd://canon-concepts "Canonical concept pages"' in installation
    assert (
        'qmd context add qmd://insights-conversations "Conversation-derived research insights"'
        in installation
    )
    assert (
        'qmd context add qmd://insights-ideas "Idea drafts and later validation assets"'
        in installation
    )
    assert (
        'qmd context add qmd://raw-evidence "Raw captured evidence and source markdown"'
        in installation
    )
    assert "`qmd` owns formal search" in architecture
    assert "/get" in commands
    assert "uv run pytest -q" in testing
    assert "uv run python -m compileall -q server tests" in testing
    assert "MCP Surface Smoke Check" in testing


def test_mcp_surface_exposes_v3_tool_names() -> None:
    tools = asyncio.run(mcp.list_tools())
    names = {tool.name for tool in tools}
    required = {
        "status",
        "kb_search",
        "kb_get",
        "discover_papers",
        "ingest_and_read",
        "check_concept_alias",
        "upsert_wiki_page",
        "merge_concept",
    }

    assert required <= names
    assert "check-concept-alias" not in names
    assert "upsert-wiki-page" not in names
