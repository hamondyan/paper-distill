from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from server.v3_markdown import render_markdown, split_frontmatter
from server.v3_names import slugify, surface_key


_WIKILINK_RE = re.compile(
    r"\[\[(?P<target>[^\]|#]+)(?P<section>#[^\]|]+)?(?P<label>\|[^\]]+)?\]\]"
)
_FOOTER_CUES = ("related:", "see also:", "links:", "references:")
FOLLOW_UP: list[str] = [
    "Run qmd update after all writes in this round finish.",
    "Run qmd embed -f after all writes finish if semantic retrieval must reflect the new state immediately.",
]


def _surface_key(value: str) -> str:
    normalized = value.casefold().strip()
    if normalized.isascii():
        return slugify(normalized)
    return surface_key(normalized)


def _frontmatter_line_count(text: str) -> int:
    if not text.startswith("---\n"):
        return 0
    try:
        _, remainder = text.split("---\n", 1)
        fm_text, _body = remainder.split("\n---\n", 1)
    except ValueError:
        return 0
    return len([line for line in fm_text.splitlines() if line.strip()])


def _repeated_link_issues(path: Path, text: str) -> list[dict[str, str]]:
    issues: list[dict[str, str]] = []
    block_lines: list[str] = []
    block_start = 1

    def check_block(lines: list[str], start_line: int) -> None:
        if not lines:
            return
        block = "\n".join(lines)
        seen: set[str] = set()
        for match in _WIKILINK_RE.finditer(block):
            target = match.group("target").strip()
            if target in seen:
                issues.append(
                    {
                        "code": "repeated_link",
                        "path": str(path),
                        "target": target,
                        "line": str(start_line),
                    }
                )
                break
            seen.add(target)

    for line_no, line in enumerate(text.splitlines(), start=1):
        if not line.strip():
            check_block(block_lines, block_start)
            block_lines = []
            block_start = line_no + 1
            continue
        if not block_lines:
            block_start = line_no
        block_lines.append(line)
    check_block(block_lines, block_start)
    return issues


def _is_well_formed_link(match: re.Match[str]) -> bool:
    parts = [match.group("target"), match.group("section") or "", match.group("label") or ""]
    for index, part in enumerate(parts):
        if not part:
            continue
        value = part[1:] if index > 0 else part
        if not value or value != value.strip() or "[" in value or "]" in value:
            return False
    return True


def _malformed_link_issues(path: Path, text: str) -> list[dict[str, str]]:
    issues: list[dict[str, str]] = []
    for line_no, line in enumerate(text.splitlines(), start=1):
        for match in _WIKILINK_RE.finditer(line):
            if not _is_well_formed_link(match):
                issues.append({"code": "malformed_link", "path": str(path), "line": str(line_no)})
                break
        unmatched = _WIKILINK_RE.sub("", line)
        if "[[" in unmatched or "]]" in unmatched:
            issues.append({"code": "malformed_link", "path": str(path), "line": str(line_no)})
    return issues


def _as_aliases(value: Any) -> list[str]:
    if isinstance(value, str):
        return [value]
    if isinstance(value, list):
        return [item for item in value if isinstance(item, str)]
    return []


def _heading(body: str) -> str:
    return next((line[2:].strip() for line in body.splitlines() if line.startswith("# ")), "")


def _known_surfaces_and_alias_issues(vault_path: Path) -> tuple[set[str], list[dict[str, str]]]:
    known: set[str] = set()
    surface_owners: dict[str, set[str]] = {}

    for path in sorted((vault_path / "wiki").rglob("*.md")):
        text = path.read_text(encoding="utf-8")
        frontmatter, body, _has_frontmatter = split_frontmatter(text)

        base_surfaces = (
            path.stem,
            str(frontmatter.get("concept") or ""),
            str(frontmatter.get("title") or ""),
            str(frontmatter.get("name") or ""),
            _heading(body),
        )
        for surface in base_surfaces:
            key = _surface_key(surface)
            if key:
                known.add(key)

        if path.parent.name == "concepts":
            canonical = str(frontmatter.get("concept") or _heading(body) or path.stem)
            owner = canonical.strip() or path.stem
            for surface in base_surfaces:
                key = _surface_key(surface)
                if key:
                    surface_owners.setdefault(key, set()).add(owner)
            for alias in _as_aliases(frontmatter.get("aliases")):
                key = _surface_key(alias)
                if not key:
                    continue
                known.add(key)
                surface_owners.setdefault(key, set()).add(owner)

    issues: list[dict[str, str]] = []
    for surface_key, owners in sorted(surface_owners.items()):
        distinct_owners = sorted(owners)
        if len(distinct_owners) > 1:
            issues.append(
                {
                    "code": "alias_ambiguity",
                    "surface": surface_key,
                    "owners": ", ".join(distinct_owners),
                }
            )
    return known, issues


def _link_quality_issues(path: Path, text: str, known_surfaces: set[str]) -> list[dict[str, str]]:
    issues: list[dict[str, str]] = []
    lines = text.splitlines()
    footer_start = max(1, len(lines) - 7)
    footer_link_count = 0
    has_footer_cue = False
    reported_footer = False

    for line_no, line in enumerate(lines, start=1):
        matches = list(_WIKILINK_RE.finditer(line))
        if line_no >= footer_start:
            footer_link_count += len(matches)
            has_footer_cue = has_footer_cue or any(cue in line.casefold() for cue in _FOOTER_CUES)
        if len(matches) >= 4 and line_no >= footer_start:
            issues.append({"code": "template_footer_link", "path": str(path), "line": str(line_no)})
            reported_footer = True
        for match in matches:
            target = match.group("target").strip()
            key = _surface_key(target)
            if key and key not in known_surfaces:
                issues.append(
                    {
                        "code": "dead_link",
                        "path": str(path),
                        "target": target,
                        "line": str(line_no),
                    }
                )
    if not reported_footer and has_footer_cue and footer_link_count >= 3:
        issues.append({"code": "template_footer_link", "path": str(path)})
    return issues


def lint_vault_v3(vault_path: Path) -> dict[str, Any]:
    known_surfaces, issues = _known_surfaces_and_alias_issues(vault_path)
    for path in sorted(vault_path.rglob("*.md")):
        text = path.read_text(encoding="utf-8")
        if _frontmatter_line_count(text) > 20:
            issues.append({"code": "frontmatter_too_large", "path": str(path)})
        if "[[" in text or "]]" in text:
            issues.extend(_malformed_link_issues(path, text))
            issues.extend(_repeated_link_issues(path, text))
            issues.extend(_link_quality_issues(path, text, known_surfaces))
    return {"ok": True, "issues": issues}


def _find_concept_paths(vault_path: Path, concept: str) -> list[Path]:
    concept_dir = vault_path / "wiki" / "concepts"
    concept_key = _surface_key(concept)
    matches: set[Path] = set()

    for path in sorted(concept_dir.glob("*.md")):
        text = path.read_text(encoding="utf-8")
        frontmatter, body, _has_frontmatter = split_frontmatter(text)
        canonical = str(frontmatter.get("concept") or frontmatter.get("title") or "").strip()
        for surface in (path.stem, canonical, _heading(body)):
            if _surface_key(surface) == concept_key:
                matches.add(path)
    return sorted(matches)


def _rewrite_links(text: str, old: str, new: str) -> tuple[str, int]:
    replacements = 0

    def replace(match: re.Match[str]) -> str:
        nonlocal replacements
        target = match.group("target").strip()
        if target != old:
            return match.group(0)
        replacements += 1
        section = match.group("section") or ""
        label = match.group("label") or ""
        return f"[[{new}{section}{label}]]"

    return _WIKILINK_RE.sub(replace, text), replacements


def _add_alias_to_concept(path: Path, alias: str) -> bool:
    text = path.read_text(encoding="utf-8")
    frontmatter, body, has_frontmatter = split_frontmatter(text)
    aliases = frontmatter.get("aliases", [])
    if isinstance(aliases, str):
        aliases = [aliases]
    if not isinstance(aliases, list):
        aliases = []

    existing = {str(item) for item in aliases}
    if alias in existing:
        return False

    aliases.append(alias)
    frontmatter["aliases"] = aliases
    rendered = (
        render_markdown(frontmatter, body)
        if has_frontmatter
        else render_markdown({"aliases": aliases}, text)
    )
    path.write_text(rendered, encoding="utf-8")
    return True


def merge_concept_v3(vault_path: Path, old: str, new: str) -> dict[str, Any]:
    old = old.strip()
    new = new.strip()
    if not old or not new:
        return {"ok": False, "error": "old and new are required", "warnings": []}

    concept_paths = _find_concept_paths(vault_path, new)
    if not concept_paths:
        return {"ok": False, "error": f"target concept not found: {new}", "warnings": []}
    if len(concept_paths) > 1:
        return {
            "ok": False,
            "error": f"ambiguous target concept: {new}",
            "candidates": [str(path) for path in concept_paths],
            "warnings": [],
        }
    concept_path = concept_paths[0]

    rewritten_files: list[str] = []
    rewritten_links = 0
    for path in sorted(vault_path.rglob("*.md")):
        text = path.read_text(encoding="utf-8")
        updated, count = _rewrite_links(text, old, new)
        if count:
            path.write_text(updated, encoding="utf-8")
            rewritten_files.append(str(path))
            rewritten_links += count

    alias_added = _add_alias_to_concept(concept_path, old)

    return {
        "ok": True,
        "old": old,
        "new": new,
        "concept_path": str(concept_path),
        "rewritten_files": rewritten_files,
        "rewritten_links": rewritten_links,
        "alias_added": alias_added,
        "follow_up": list(FOLLOW_UP),
    }
