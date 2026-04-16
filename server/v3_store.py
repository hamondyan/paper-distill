from __future__ import annotations

from pathlib import Path
from typing import Any

from server.v3_bootstrap import ensure_v3_layout
from server.v3_markdown import atomic_write_text, render_markdown


FOLLOW_UP: list[str] = [
    "Run qmd update after all writes in this round finish.",
    "Run qmd embed -f after all writes finish if semantic retrieval must reflect the new state immediately.",
]


_PAGE_DIRS: dict[str, tuple[str, ...]] = {
    "paper": ("wiki", "papers"),
    "concept": ("wiki", "concepts"),
    "idea": ("insights", "ideas"),
    "conversation": ("insights", "conversations"),
}


def _target_path(vault_path: Path, page_type: str, target: str) -> Path:
    page_dirs = _PAGE_DIRS.get(page_type)
    if page_dirs is None:
        raise ValueError(
            f"unsupported page_type: {page_type}. Expected one of: "
            + ", ".join(sorted(_PAGE_DIRS))
        )
    return vault_path.joinpath(*page_dirs, f"{target}.md")


def upsert_wiki_page_v3(
    vault_path: Path,
    page_type: str,
    target: str,
    frontmatter: dict,
    body: str,
) -> dict[str, Any]:
    target = target.strip()
    if not target:
        return {"ok": False, "error": "target is required", "warnings": []}
    if any(sep in target for sep in ("/", "\\", "..")):
        return {"ok": False, "error": "target must not contain path separators", "warnings": []}

    try:
        path = _target_path(vault_path, page_type, target)
    except ValueError as exc:
        return {"ok": False, "error": str(exc), "warnings": []}

    ensure_v3_layout(vault_path)

    payload = dict(frontmatter or {})
    payload["type"] = page_type

    try:
        atomic_write_text(path, render_markdown(payload, body))
    except Exception as exc:  # pragma: no cover - defensive path
        return {"ok": False, "error": str(exc), "warnings": []}

    return {"ok": True, "path": str(path), "follow_up": FOLLOW_UP}
