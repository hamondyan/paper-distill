from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from server.paper_utils import normalise_title
from server.v3_bootstrap import ensure_v3_layout
from server.v3_markdown import atomic_write_text, render_markdown, split_frontmatter


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
_WIKILINK_RE = re.compile(
    r"\[\[(?P<target>[^\]|#]+)(?P<section>#[^\]|]+)?(?P<label>\|[^\]]+)?\]\]"
)


def _target_path(vault_path: Path, page_type: str, target: str) -> Path:
    page_dirs = _PAGE_DIRS.get(page_type)
    if page_dirs is None:
        raise ValueError(
            f"unsupported page_type: {page_type}. Expected one of: "
            + ", ".join(sorted(_PAGE_DIRS))
        )
    return vault_path.joinpath(*page_dirs, f"{target}.md")


def _non_empty_string(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip())


def _string_list(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    return [item.strip() for item in value if isinstance(item, str) and item.strip()]


def _wikilink_targets(body: str) -> set[str]:
    return {
        normalise_title(match.group("target").strip())
        for match in _WIKILINK_RE.finditer(body)
        if match.group("target").strip()
    }


def _validate_paper_page(frontmatter: dict[str, Any], body: str) -> list[str]:
    errors: list[str] = []
    for field in ("paper_id", "title", "venue", "source_layer"):
        if not _non_empty_string(frontmatter.get(field)):
            errors.append(f"paper frontmatter requires non-empty {field}")
    year = frontmatter.get("year")
    if isinstance(year, bool) or not isinstance(year, int):
        errors.append("paper frontmatter requires integer year")

    key_concepts = _string_list(frontmatter.get("key_concepts_topk"))
    if not 1 <= len(key_concepts) <= 5:
        errors.append("paper key_concepts_topk must contain 1 to 5 concepts")
    if len(set(map(normalise_title, key_concepts))) != len(key_concepts):
        errors.append("paper key_concepts_topk must not contain duplicate concepts")

    if key_concepts:
        linked = _wikilink_targets(body)
        expected = {normalise_title(concept) for concept in key_concepts}
        if not linked.intersection(expected):
            errors.append("paper body must link at least one key concept from key_concepts_topk")
    return errors


def _validate_concept_page(frontmatter: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    if not _non_empty_string(frontmatter.get("concept")):
        errors.append("concept frontmatter requires non-empty concept")
    if not isinstance(frontmatter.get("aliases"), list):
        errors.append("concept aliases must be a list")
    if not _non_empty_string(frontmatter.get("source_layer")):
        errors.append("concept frontmatter requires non-empty source_layer")
    if not _string_list(frontmatter.get("related_papers_topk")):
        errors.append("concept related_papers_topk must contain at least one supporting paper")
    return errors


def _quality_errors(page_type: str, frontmatter: dict[str, Any], body: str) -> list[str]:
    if page_type == "paper":
        return _validate_paper_page(frontmatter, body)
    if page_type == "concept":
        return _validate_concept_page(frontmatter)
    return []


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

    payload = dict(frontmatter or {})
    payload["type"] = page_type
    errors = _quality_errors(page_type, payload, body)
    if errors:
        return {"ok": False, "error": "; ".join(errors), "warnings": []}

    ensure_v3_layout(vault_path)

    try:
        atomic_write_text(path, render_markdown(payload, body))
    except Exception as exc:  # pragma: no cover - defensive path
        return {"ok": False, "error": str(exc), "warnings": []}

    return {"ok": True, "path": str(path), "follow_up": list(FOLLOW_UP)}


_AUDIT_PAGE_TYPES: tuple[str, ...] = ("paper", "concept")


def audit_wiki_schema(vault_path: Path) -> list[dict[str, Any]]:
    """Scan wiki pages and return schema violations without modifying files."""
    violations: list[dict[str, Any]] = []
    for page_type in _AUDIT_PAGE_TYPES:
        page_dir = vault_path.joinpath(*_PAGE_DIRS[page_type])
        if not page_dir.is_dir():
            continue
        for md_path in sorted(page_dir.glob("*.md")):
            try:
                text = md_path.read_text(encoding="utf-8")
            except OSError as exc:
                violations.append(
                    {"page_type": page_type, "path": str(md_path), "errors": [f"read error: {exc}"]}
                )
                continue
            frontmatter, body, _ = split_frontmatter(text)
            errors = _quality_errors(page_type, frontmatter, body)
            if errors:
                violations.append(
                    {"page_type": page_type, "path": str(md_path), "errors": errors}
                )
    return violations
