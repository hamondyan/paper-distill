from __future__ import annotations

from pathlib import Path


def test_retired_system_names_are_not_present() -> None:
    repo_root = Path(__file__).resolve().parents[1]
    checked_roots = [
        repo_root / "server",
        repo_root / "tests",
        repo_root / "docs",
        repo_root / "commands",
        repo_root / "hooks",
        repo_root / "skills",
        repo_root / "templates",
        repo_root / "scripts",
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
        '"' + "raw" + '"',
        "'" + "raw" + "'",
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
