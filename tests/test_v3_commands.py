from __future__ import annotations

import asyncio
from pathlib import Path

from server.server import mcp


REPO_ROOT = Path(__file__).resolve().parents[1]
EXPECTED_COMMANDS = {"approve", "discover", "inbox", "ingest", "lint"}
EXPECTED_MCP_TOOLS = {
    "approve_papers",
    "discover_papers",
    "ingest_and_read",
    "check_concept_alias",
    "upsert_wiki_page",
    "merge_concept",
    "lint_vault",
}
EXPECTED_ROOT_DOCS = {
    "README.md",
    "architecture.md",
    "commands.md",
    "configuration.md",
    "frontmatter-reference.md",
    "installation.md",
    "qmd-cli.md",
    "testing.md",
    "vault-layout.md",
}


def test_command_inventory_matches_v3_surface() -> None:
    names = {path.stem for path in (REPO_ROOT / "commands").glob("*.md")}
    assert names == EXPECTED_COMMANDS


def test_root_docs_inventory_matches_v3_public_docs() -> None:
    docs_root = REPO_ROOT / "docs"
    names = {path.name for path in docs_root.glob("*.md")}
    assert names == EXPECTED_ROOT_DOCS


def test_superpowers_process_artifacts_are_absent_from_docs() -> None:
    superpowers_root = REPO_ROOT / "docs" / "superpowers"
    assert not superpowers_root.exists()


def test_public_command_docs_point_to_v3_tools() -> None:
    approve_doc = (REPO_ROOT / "commands/approve.md").read_text(encoding="utf-8")
    discover_doc = (REPO_ROOT / "commands/discover.md").read_text(encoding="utf-8")
    inbox_doc = (REPO_ROOT / "commands/inbox.md").read_text(encoding="utf-8")
    ingest_doc = (REPO_ROOT / "commands/ingest.md").read_text(encoding="utf-8")
    lint_doc = (REPO_ROOT / "commands/lint.md").read_text(encoding="utf-8")

    assert "approve_papers" in approve_doc
    assert "#approved" in approve_doc
    assert "discover_papers" in discover_doc
    assert "#approved" in inbox_doc
    assert "ingest_and_read" in ingest_doc
    assert "qmd update" in ingest_doc
    assert "qmd embed -f" in ingest_doc
    assert "lint_vault" in lint_doc


def test_ingest_command_documents_agent_resolved_batch_inputs() -> None:
    ingest_doc = Path("commands/ingest.md").read_text(encoding="utf-8")

    assert "agent resolves" in ingest_doc
    assert "multiple resolved arXiv" in ingest_doc
    assert "openvla" in ingest_doc


def test_public_docs_describe_v3_qmd_cutover() -> None:
    readme = (REPO_ROOT / "README.md").read_text(encoding="utf-8")
    docs_index = (REPO_ROOT / "docs/README.md").read_text(encoding="utf-8")
    installation = (REPO_ROOT / "docs/installation.md").read_text(encoding="utf-8")
    architecture = (REPO_ROOT / "docs/architecture.md").read_text(encoding="utf-8")
    commands = (REPO_ROOT / "docs/commands.md").read_text(encoding="utf-8")
    testing = (REPO_ROOT / "docs/testing.md").read_text(encoding="utf-8")
    vault_layout = (REPO_ROOT / "docs/vault-layout.md").read_text(encoding="utf-8")
    qmd_cli = (REPO_ROOT / "docs/qmd-cli.md").read_text(encoding="utf-8")

    assert "qmd as the read/index path" in readme
    assert "docs/qmd-cli.md" in readme
    assert "qmd-cli.md" in docs_index
    assert "paper-distill-admin bootstrap" in installation
    assert "creates the vault layout and initializes the QMD collections and contexts" in installation
    assert "docs/qmd-cli.md" in installation
    assert "QMD CLI is the only read/index path" in architecture
    assert "business MCP" in architecture
    assert "docs/qmd-cli.md" in commands
    assert "/discover" in commands
    assert "/approve" in commands
    assert "/lint" in commands
    assert "/get" not in commands
    assert "uv run python -m pytest -q" in testing
    assert "uv run python -m compileall -q server tests" in testing
    assert "business surface" in testing
    assert "qmd --help" in testing
    assert "QMD CLI is the primary source; command details follow the runtime output of `qmd --help`." in qmd_cli
    assert "canon-papers" in qmd_cli
    assert "canon-concepts" in qmd_cli
    assert "insights-conversations" in qmd_cli
    assert "insights-ideas" in qmd_cli
    assert "raw-evidence" in qmd_cli
    assert "qmd query" in qmd_cli
    assert "qmd get" in qmd_cli
    assert "qmd status" in qmd_cli
    assert "qmd update" in qmd_cli
    assert "qmd embed -f" in qmd_cli
    assert "qmd collection" in qmd_cli
    assert "qmd context" in qmd_cli
    assert "qmd ls" in qmd_cli
    assert "kb_search" not in vault_layout
    assert "kb_get" not in vault_layout


def test_mcp_surface_exposes_business_tools_only() -> None:
    tools = asyncio.run(mcp.list_tools())
    names = {tool.name for tool in tools}

    assert names == EXPECTED_MCP_TOOLS
    assert "check-concept-alias" not in names
    assert "upsert-wiki-page" not in names
    assert "status" not in names
    assert "kb_search" not in names
    assert "kb_get" not in names
    assert "kb_update_index" not in names
    assert "kb_reembed_force" not in names
