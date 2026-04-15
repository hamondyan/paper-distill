from __future__ import annotations

import re
from pathlib import Path


V3_DIRS = (
    "inbox",
    "raw/evidence",
    "wiki/papers",
    "wiki/concepts",
    "insights/ideas",
    "insights/conversations",
    "exports/presentations",
    ".state",
)


def _slugify(value: str) -> str:
    lowered = value.casefold()
    cleaned = re.sub(r"[^a-z0-9]+", "-", lowered).strip("-")
    return cleaned or "untitled"


def paper_filename(title: str, paper_id: str) -> str:
    safe_id = paper_id.replace(":", "-")
    return f"{_slugify(title)}--{safe_id}.md"


def ensure_v3_layout(vault_path: Path) -> dict[str, list[str]]:
    created: list[str] = []
    for rel in V3_DIRS:
        path = vault_path / rel
        if not path.exists():
            path.mkdir(parents=True, exist_ok=True)
            created.append(rel)

    seen_path = vault_path / ".state" / "seen_papers.json"
    if not seen_path.exists():
        seen_path.write_text("{}\n", encoding="utf-8")
        created.append(".state/seen_papers.json")

    log_path = vault_path / "vault-log.md"
    if not log_path.exists():
        log_path.write_text(
            "# Vault Operation Log\n\n| Timestamp | Action | Resource ID | Status | Notes |\n|-----------|--------|-------------|--------|-------|\n",
            encoding="utf-8",
        )
        created.append("vault-log.md")

    return {"created": created}
