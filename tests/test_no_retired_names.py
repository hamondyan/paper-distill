from __future__ import annotations

from pathlib import Path


def _public_learning_paths(repo_root: Path) -> list[Path]:
    docs_root = repo_root / "docs"
    return [
        repo_root / "README.md",
        *sorted(docs_root.glob("*.md")),
        *(sorted((repo_root / "commands").glob("*.md"))),
        *(sorted((repo_root / "skills").glob("*/SKILL.md"))),
        *(sorted((repo_root / "skills").glob("*/agents/openai.yaml"))),
        repo_root / "hooks" / "session-start",
    ]


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
    assert "docs/qmd-cli.md" in skill_docs["paper-intake"]
    assert "qmd --help" in skill_docs["paper-intake"]

    assert "qmd query" in skill_docs["knowledge-workbench"]
    assert "qmd get" in skill_docs["knowledge-workbench"]
    assert "qmd status" in skill_docs["knowledge-workbench"]
    assert "qmd update" in skill_docs["knowledge-workbench"]
    assert "qmd embed -f" in skill_docs["knowledge-workbench"]
    assert "After a merge, report rewritten files, alias changes, and separate follow-up guidance for `qmd update` / `qmd embed -f` when needed." in skill_docs["knowledge-workbench"]
    assert "upsert_wiki_page" in skill_docs["knowledge-workbench"]
    assert "check_concept_alias" in skill_docs["knowledge-workbench"]
    assert "merge_concept" in skill_docs["knowledge-workbench"]
    assert "lint_vault" in skill_docs["knowledge-workbench"]
    assert "docs/qmd-cli.md" in skill_docs["knowledge-workbench"]
    assert "qmd --help" in skill_docs["knowledge-workbench"]

    assert "qmd query" in skill_docs["idea-workbench"]
    assert "qmd get" in skill_docs["idea-workbench"]
    assert "upsert_wiki_page" in skill_docs["idea-workbench"]
    assert 'page_type="idea"' in skill_docs["idea-workbench"]
    assert 'page_type="conversation"' in skill_docs["idea-workbench"]
    assert "docs/qmd-cli.md" in skill_docs["idea-workbench"]
    assert "qmd --help" in skill_docs["idea-workbench"]

    retired_wrappers = [
        "kb_search",
        "kb_get",
        "kb_update_index",
        "kb_reembed_force",
    ]
    offenders = [
        name
        for name in retired_wrappers
        if any(name in doc for doc in skill_docs.values()) or name in agent_prompts
    ]
    assert offenders == []

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


def test_public_learning_surface_teaches_qmd_cli_directly() -> None:
    repo_root = Path(__file__).resolve().parents[1]
    texts = [
        path.read_text(encoding="utf-8", errors="ignore")
        for path in _public_learning_paths(repo_root)
        if path.exists()
    ]

    combined = "\n".join(texts)
    assert (repo_root / "docs/qmd-cli.md").exists()
    assert "docs/qmd-cli.md" in combined
    assert "qmd --help" in combined
    assert "qmd query" in combined
    assert "qmd get" in combined


def test_retired_wrapper_names_are_absent_from_public_learning_surface() -> None:
    repo_root = Path(__file__).resolve().parents[1]
    banned = [
        "kb_search",
        "kb_get",
        "kb_update_index",
        "kb_reembed_force",
    ]

    offenders: list[str] = []
    for path in _public_learning_paths(repo_root):
        if not path.exists():
            continue
        text = path.read_text(encoding="utf-8", errors="ignore")
        for term in banned:
            if term in text:
                offenders.append(f"{path.relative_to(repo_root)}: {term}")

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
