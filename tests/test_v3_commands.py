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


def test_public_docs_describe_v3_qmd_cutover() -> None:
    readme = Path("README.md").read_text(encoding="utf-8")
    installation = Path("docs/installation.md").read_text(encoding="utf-8")
    architecture = Path("docs/architecture.md").read_text(encoding="utf-8")
    commands = Path("docs/commands.md").read_text(encoding="utf-8")

    assert "`qmd` is a hard dependency in v3.0" in readme
    assert "discover -> approve -> ingest -> search/get -> lint -> status" in readme
    assert "qmd collection add <vault>/insights/ideas --name insights-ideas" in installation
    assert "`qmd` owns formal search" in architecture
    assert "/get" in commands


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
