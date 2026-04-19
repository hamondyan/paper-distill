from __future__ import annotations

import asyncio
from pathlib import Path

from server.server import mcp


REPO_ROOT = Path(__file__).resolve().parents[1]
EXPECTED_COMMANDS = {"discover", "ingest", "lint", "status"}
EXPECTED_MCP_TOOLS = {
    "discover_papers",
    "ingest_and_read",
    "distill_paper",
    "distill_papers",
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
    "plugin-installation.md",
    "qmd-cli.md",
    "testing.md",
    "vault-layout.md",
}


def test_command_inventory_matches_v3_surface() -> None:
    names = {path.stem for path in (REPO_ROOT / "commands").glob("*.md")}
    assert names == EXPECTED_COMMANDS


def test_user_facing_commands_have_consistent_frontmatter() -> None:
    for command_name in EXPECTED_COMMANDS:
        command_path = REPO_ROOT / "commands" / f"{command_name}.md"
        command_doc = command_path.read_text(encoding="utf-8")

        assert command_doc.startswith("---\n")
        frontmatter = command_doc.split("---\n", 2)[1]
        assert f"name: {command_name}" in frontmatter
        assert "user-invocable: true" in frontmatter


def test_root_docs_inventory_matches_v3_public_docs() -> None:
    docs_root = REPO_ROOT / "docs"
    names = {path.name for path in docs_root.glob("*.md")}
    assert names == EXPECTED_ROOT_DOCS


def test_superpowers_process_artifacts_live_under_docs_namespace() -> None:
    readme = (REPO_ROOT / "README.md").read_text(encoding="utf-8")
    docs_index = (REPO_ROOT / "docs" / "README.md").read_text(encoding="utf-8")

    assert "docs/superpowers" not in readme
    assert "docs/superpowers" not in docs_index
    assert "superpowers" not in readme
    assert "superpowers" not in docs_index


def test_public_command_docs_point_to_v3_tools() -> None:
    discover_doc = (REPO_ROOT / "commands/discover.md").read_text(encoding="utf-8")
    ingest_doc = (REPO_ROOT / "commands/ingest.md").read_text(encoding="utf-8")
    lint_doc = (REPO_ROOT / "commands/lint.md").read_text(encoding="utf-8")
    status_doc = (REPO_ROOT / "commands/status.md").read_text(encoding="utf-8")

    assert "discover_papers" in discover_doc
    assert "ingest_and_read" in ingest_doc
    assert "qmd update" in ingest_doc
    assert "qmd embed -f" in ingest_doc
    assert "lint_vault" in lint_doc
    assert "lint_vault" in status_doc
    assert 'argument-hint: "[arxiv-url | arxiv-id | arxiv-doi]"' in ingest_doc
    assert "paper-title" not in ingest_doc
    assert "acronym" not in ingest_doc
    assert "/ingest approved" not in ingest_doc
    assert "approved" not in ingest_doc
    assert 'argument-hint: ""' in status_doc
    assert "papers, concepts, ideas, conversations, raw evidence" in status_doc
    assert "inbox" not in status_doc
    assert "#approved" not in status_doc
    assert "/ingest approved" not in status_doc
    assert "pending approvals" not in status_doc
    assert "inbox_stale" not in status_doc
    assert "inbox pending" not in status_doc
    assert "inbox approved" not in status_doc
    assert "paper_missing_required_fields" in status_doc
    assert "paper_key_concept_unlinked" in status_doc
    assert "concept_not_linked_in_body" not in status_doc


def test_ingest_command_documents_agent_resolved_batch_inputs() -> None:
    ingest_doc = Path("commands/ingest.md").read_text(encoding="utf-8")

    assert "agent resolves" in ingest_doc
    assert "multiple resolved arXiv" in ingest_doc
    assert "10.48550/arxiv.2410.24164, 1706.03762" in ingest_doc
    assert "resolved arXiv URLs, arXiv IDs, or arXiv DOI values" in ingest_doc
    assert "URLs, IDs, or DOIs" not in ingest_doc


def test_public_docs_describe_v3_qmd_cutover() -> None:
    readme = (REPO_ROOT / "README.md").read_text(encoding="utf-8")
    docs_index = (REPO_ROOT / "docs/README.md").read_text(encoding="utf-8")
    installation = (REPO_ROOT / "docs/installation.md").read_text(encoding="utf-8")
    architecture = (REPO_ROOT / "docs/architecture.md").read_text(encoding="utf-8")
    commands = (REPO_ROOT / "docs/commands.md").read_text(encoding="utf-8")
    frontmatter = (REPO_ROOT / "docs/frontmatter-reference.md").read_text(encoding="utf-8")
    testing = (REPO_ROOT / "docs/testing.md").read_text(encoding="utf-8")
    vault_layout = (REPO_ROOT / "docs/vault-layout.md").read_text(encoding="utf-8")
    qmd_cli = (REPO_ROOT / "docs/qmd-cli.md").read_text(encoding="utf-8")

    assert "qmd as the read/index path" in readme
    assert "docs/qmd-cli.md" in readme
    assert "chat-only discovery" in readme
    assert "/ingest https://arxiv.org/abs/2410.24164" in readme
    assert "/ingest 10.48550/arxiv.2410.24164" in readme
    assert "/ingest 1706.03762" in readme
    assert "openvla, octo, diffusion policy" not in readme
    assert "inbox/" not in readme
    assert "qmd-cli.md" in docs_index
    assert "chat-only discovery" in docs_index
    assert "paper-distill-admin bootstrap" in installation
    assert "creates the vault layout and initializes the QMD collections and contexts" in installation
    assert "docs/qmd-cli.md" in installation
    assert "QMD CLI is the only read/index path" in architecture
    assert "business MCP" in architecture
    assert "discover -> ingest resolved arXiv references -> distill_paper -> qmd update -> lint" in architecture
    assert "distill_paper(input_value, distilled=None)" in architecture
    assert "distill_papers(items)" in architecture
    assert "docs/qmd-cli.md" in commands
    assert "/discover" in commands
    assert "/approve" not in commands
    assert "approve_papers" not in commands
    assert "ingest approved" not in commands
    assert "exact titles" not in commands
    assert "acronyms" not in commands
    assert "aliases" not in commands
    assert "project names" not in commands
    assert "resolved arXiv URLs, IDs, or arXiv DOI values" in commands
    assert "/lint" in commands
    assert "/status" in commands
    assert "distill_paper" in commands
    assert "discover -> ingest resolved arXiv references -> distill_paper -> qmd update -> lint" in commands
    assert "paper pages without matching raw evidence" in commands
    assert "decorative concept links" in commands
    assert "papers, concepts, ideas, conversations, raw evidence" in commands
    assert "inbox pending" not in commands
    assert "inbox approved" not in commands
    assert "/get" not in commands
    assert "1-to-5 range" in frontmatter
    assert "paper_without_raw_evidence" in frontmatter
    assert "Inbox Stub" not in frontmatter
    assert "agent-authored canonical pages usually use `wiki`" in frontmatter
    assert "uv run python -m pytest -q" in testing
    assert "uv run python -m compileall -q server tests" in testing
    assert "business surface" in testing
    assert "distill_papers" in testing
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
    assert "seen_papers.json" not in vault_layout
    public_docs = "\n".join([readme, docs_index, installation, architecture, commands, frontmatter, testing, vault_layout, qmd_cli])
    assert "/ingest approved" not in public_docs
    assert "approve_papers" not in public_docs
    assert "#approved" not in public_docs


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
