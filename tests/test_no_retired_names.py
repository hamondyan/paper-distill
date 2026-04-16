from __future__ import annotations

from pathlib import Path


def test_retired_system_names_are_not_present() -> None:
    repo_root = Path(__file__).resolve().parents[1]
    checked_roots = [
        repo_root / "agents",
        repo_root / ".codex-plugin",
        repo_root / ".claude-plugin",
        repo_root / ".mcp.json",
        repo_root / "hooks",
        repo_root / "docs",
        repo_root / "commands",
        repo_root / "skills",
        repo_root / "README.md",
        repo_root / "settings.example.json",
        repo_root / "pyproject.toml",
    ]
    ignored = {Path(__file__).resolve()}
    banned = [
        "mutation" + "_" + "queue",
        "publish" + "_" + "journal",
        "daily" + "-" + "log",
        "Paper Distill" + "/" + "raw",
        "mutation" + "_" + "id",
        "memory" + "_" + "mutation" + "_" + "id",
        "payload" + "_" + "json",
        "execute_" + "memory" + "_",
        "execute_" + "dialogue" + "_",
        "execute_" + "idea" + "_",
        "execute_" + "compile" + "_",
        "schema" + "_" + "version=" + '"' + "legacy" + '"',
        "migration tool for existing vaults",
        "compatibility entry",
        "legacy verification snapshot",
        "killed" + "-" + "ideas",
        "verification snapshot",
        "v" + "2",
        "v" + "2.1",
        "2" + ".1",
        "leg" + "acy",
        "mig" + "ration",
        "compatibility" + " layer",
        "query" + "-" + "library",
        "source" + "-" + "discover",
        "source" + "-" + "ingest",
        "read" + "-" + "paper",
        "search" + "-" + "papers",
        "paper" + "-" + "distill" + "-" + "extract",
        "knowledge" + "-" + "compile" + "-",
        "compile" + "_" + "state",
        ".state" + "/" + "ir",
        "vault" + "-" + "health",
        "write" + "-" + "wiki",
        "concept" + " registry",
        "concept" + "_" + "registry",
        "zo" + "tero",
        "obsidian" + "_" + "query",
        "Paper Distill" + "/",
        "sources" + "/" + "evidence",
        "wiki" + "/" + "methods",
        "wiki" + "/" + "topics",
        "insights" + "/" + "queries",
        "memory" + "/",
        "conversation" + "-" + "memory",
        "conversation" + " memory",
        "Zo" + "tero",
        "ZO" + "TERO",
        "2" + ".1" + ".0",
        "CR" + "GP" + "-DNL",
        "search" + "_" + "papers",
        "raw" + "/" + "_index.md",
        "compiled" + ": true",
        "wiki" + " compilation",
    ]

    offenders: list[str] = []
    for root in checked_roots:
        if not root.exists():
            continue
        paths = [root] if root.is_file() else [p for p in root.rglob("*") if p.is_file()]
        for path in paths:
            if path in ignored:
                continue
            if any(part in {".git", ".venv", ".pytest_cache", ".ruff_cache", "__pycache__"} for part in path.parts):
                continue
            text = path.read_text(encoding="utf-8", errors="ignore")
            for term in banned:
                if term in text:
                    offenders.append(f"{path.relative_to(repo_root)}: {term}")

    assert offenders == []


def test_top_level_agents_surface_is_removed() -> None:
    repo_root = Path(__file__).resolve().parents[1]
    assert not (repo_root / "agents").exists()


def test_skills_route_through_v3_tools_only() -> None:
    repo_root = Path(__file__).resolve().parents[1]
    skills_root = repo_root / "skills"
    skill_docs = {
        path.parent.name: path.read_text(encoding="utf-8")
        for path in sorted(skills_root.glob("*/SKILL.md"))
    }
    agent_prompts = "\n".join(
        path.read_text(encoding="utf-8")
        for path in sorted(skills_root.glob("*/agents/openai.yaml"))
    )

    assert "discover_papers" in skill_docs["paper-intake"]
    assert "ingest_and_read" in skill_docs["paper-intake"]
    assert "#approved" in skill_docs["paper-intake"]
    assert "raw/evidence" in skill_docs["paper-intake"]

    assert "kb_search" in skill_docs["knowledge-workbench"]
    assert "kb_get" in skill_docs["knowledge-workbench"]
    assert "upsert_wiki_page" in skill_docs["knowledge-workbench"]
    assert "check_concept_alias" in skill_docs["knowledge-workbench"]
    assert "merge_concept" in skill_docs["knowledge-workbench"]
    assert "lint_vault" in skill_docs["knowledge-workbench"]
    assert "kb_update_index" in skill_docs["knowledge-workbench"]
    assert "kb_reembed_force" in skill_docs["knowledge-workbench"]
    assert "status" in skill_docs["knowledge-workbench"]

    assert "kb_search" in skill_docs["idea-workbench"]
    assert "kb_get" in skill_docs["idea-workbench"]
    assert "upsert_wiki_page" in skill_docs["idea-workbench"]
    assert 'page_type="idea"' in skill_docs["idea-workbench"]
    assert 'page_type="conversation"' in skill_docs["idea-workbench"]

    retired = [
        "query" + "-" + "library",
        "source" + "-" + "discover",
        "source" + "-" + "ingest",
        "read" + "-" + "paper",
        "search" + "-" + "papers",
        "idea" + "-" + "analyze",
        "write" + "-" + "wiki",
        "vault" + "-" + "health",
        "knowledge" + "-" + "compile" + "-",
        "paper" + "-" + "distill" + "-" + "extract",
    ]
    combined = "\n".join(skill_docs.values()) + "\n" + agent_prompts
    offenders = [term for term in retired if term in combined]
    assert offenders == []


def test_conversation_insight_wording_has_no_memory_terms() -> None:
    repo_root = Path(__file__).resolve().parents[1]
    checked_roots = [
        repo_root / "README.md",
        repo_root / "docs",
        repo_root / "commands",
        repo_root / "skills",
        repo_root / "server",
        repo_root / "tests",
    ]
    ignored = {Path(__file__).resolve()}
    banned = [
        "conversation" + "-" + "memory",
        "conversation" + " memory",
        "v3" + "_" + "memory",
        "write" + "_" + "conversation" + "_" + "memory",
    ]

    offenders: list[str] = []
    for root in checked_roots:
        paths = [root] if root.is_file() else [p for p in root.rglob("*") if p.is_file()]
        for path in paths:
            if path in ignored:
                continue
            if any(part in {".git", ".venv", ".pytest_cache", ".ruff_cache", "__pycache__"} for part in path.parts):
                continue
            text = path.read_text(encoding="utf-8", errors="ignore")
            for term in banned:
                if term in text:
                    offenders.append(f"{path.relative_to(repo_root)}: {term}")

    assert offenders == []
