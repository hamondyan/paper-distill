from __future__ import annotations

import re
from io import StringIO
from pathlib import Path
from typing import Any

import yaml

from server.concept_registry import slugify
from server.qmd_runtime import qmd_reembed_force, qmd_update


_WIKILINK_RE = re.compile(
    r"\[\[(?P<target>[^\]|#]+)(?P<section>#[^\]|]+)?(?P<label>\|[^\]]+)?\]\]"
)
_NON_WORD_RE = re.compile(r"[\W_]+", re.UNICODE)


def _surface_key(value: str) -> str:
    normalized = value.casefold().strip()
    if normalized.isascii():
        return slugify(normalized)
    return _NON_WORD_RE.sub("", normalized)


def _split_frontmatter(text: str) -> tuple[dict[str, Any], str, bool]:
    if not text.startswith("---\n"):
        return {}, text, False
    try:
        _, remainder = text.split("---\n", 1)
        fm_text, body = remainder.split("\n---\n", 1)
    except ValueError:
        return {}, text, False
    frontmatter = yaml.safe_load(fm_text) or {}
    if not isinstance(frontmatter, dict):
        frontmatter = {}
    return frontmatter, body, True


def _render_markdown(frontmatter: dict[str, Any], body: str) -> str:
    stream = StringIO()
    stream.write("---\n")
    stream.write(
        yaml.safe_dump(
            frontmatter,
            sort_keys=False,
            allow_unicode=True,
            default_flow_style=False,
        ).strip()
    )
    stream.write("\n---\n")
    stream.write(body)
    return stream.getvalue()


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
    for line_no, line in enumerate(text.splitlines(), start=1):
        seen: set[str] = set()
        for match in _WIKILINK_RE.finditer(line):
            target = match.group("target").strip()
            if target in seen:
                issues.append(
                    {
                        "code": "repeated_link",
                        "path": str(path),
                        "target": target,
                        "line": str(line_no),
                    }
                )
                break
            seen.add(target)
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
    alias_owners: dict[str, list[str]] = {}

    for path in sorted((vault_path / "wiki").rglob("*.md")):
        text = path.read_text(encoding="utf-8")
        try:
            frontmatter, body, _has_frontmatter = _split_frontmatter(text)
        except yaml.YAMLError:
            frontmatter, body = {}, text

        for surface in (
            path.stem,
            str(frontmatter.get("concept") or ""),
            str(frontmatter.get("title") or ""),
            str(frontmatter.get("name") or ""),
            _heading(body),
        ):
            key = _surface_key(surface)
            if key:
                known.add(key)

        if path.parent.name == "concepts":
            canonical = str(frontmatter.get("concept") or _heading(body) or path.stem)
            for alias in _as_aliases(frontmatter.get("aliases")):
                key = _surface_key(alias)
                if not key:
                    continue
                known.add(key)
                alias_owners.setdefault(key, []).append(canonical)

    issues: list[dict[str, str]] = []
    for alias_key, owners in sorted(alias_owners.items()):
        distinct_owners = sorted(set(owners))
        if len(distinct_owners) > 1:
            issues.append(
                {
                    "code": "alias_ambiguity",
                    "alias": alias_key,
                    "owners": ", ".join(distinct_owners),
                }
            )
    return known, issues


def _link_quality_issues(path: Path, text: str, known_surfaces: set[str]) -> list[dict[str, str]]:
    issues: list[dict[str, str]] = []
    lines = text.splitlines()
    footer_start = max(1, len(lines) - 7)

    for line_no, line in enumerate(lines, start=1):
        matches = list(_WIKILINK_RE.finditer(line))
        if len(matches) >= 4 and line_no >= footer_start:
            issues.append({"code": "template_footer_link", "path": str(path), "line": str(line_no)})
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
    return issues


def lint_vault_v3(vault_path: Path) -> dict[str, Any]:
    known_surfaces, issues = _known_surfaces_and_alias_issues(vault_path)
    for path in sorted(vault_path.rglob("*.md")):
        text = path.read_text(encoding="utf-8")
        if _frontmatter_line_count(text) > 20:
            issues.append({"code": "frontmatter_too_large", "path": str(path)})
        if "[[" in text or "]]" in text:
            if text.count("[[") != text.count("]]"):
                issues.append({"code": "malformed_link", "path": str(path)})
            issues.extend(_repeated_link_issues(path, text))
            issues.extend(_link_quality_issues(path, text, known_surfaces))
    return {"ok": True, "issues": issues}


def _find_concept_path(vault_path: Path, concept: str) -> Path | None:
    concept_dir = vault_path / "wiki" / "concepts"
    direct_path = concept_dir / f"{concept}.md"
    if direct_path.exists():
        return direct_path

    for path in sorted(concept_dir.glob("*.md")):
        text = path.read_text(encoding="utf-8")
        try:
            frontmatter, body, _has_frontmatter = _split_frontmatter(text)
        except yaml.YAMLError:
            continue
        canonical = str(frontmatter.get("concept") or frontmatter.get("title") or "").strip()
        heading = next(
            (line[2:].strip() for line in body.splitlines() if line.startswith("# ")),
            "",
        )
        if concept in {path.stem, canonical, heading}:
            return path
    return None


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
    frontmatter, body, has_frontmatter = _split_frontmatter(text)
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
    rendered = _render_markdown(frontmatter, body) if has_frontmatter else _render_markdown({"aliases": aliases}, text)
    path.write_text(rendered, encoding="utf-8")
    return True


def merge_concept_v3(vault_path: Path, old: str, new: str) -> dict[str, Any]:
    old = old.strip()
    new = new.strip()
    if not old or not new:
        return {"ok": False, "error": "old and new are required", "warnings": []}

    concept_path = _find_concept_path(vault_path, new)
    if concept_path is None:
        return {"ok": False, "error": f"target concept not found: {new}", "warnings": []}

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

    warnings: list[str] = []
    update_result = qmd_update(vault_path)
    reembed_result = qmd_reembed_force(vault_path)
    for label, result in (("qmd update", update_result), ("qmd reembed", reembed_result)):
        if not result.get("ok", False):
            warnings.append(f"{label} failed: {result.get('error') or 'unknown error'}")

    return {
        "ok": True,
        "old": old,
        "new": new,
        "concept_path": str(concept_path),
        "rewritten_files": rewritten_files,
        "rewritten_links": rewritten_links,
        "alias_added": alias_added,
        "update": update_result,
        "reembed": reembed_result,
        "warnings": warnings,
    }
