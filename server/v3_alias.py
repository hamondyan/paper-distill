from __future__ import annotations

import re
from pathlib import Path
from typing import Any

import yaml

from server.concept_registry import slugify

_NON_WORD_RE = re.compile(r"[\W_]+", re.UNICODE)


def _normalize(value: str) -> str:
    normalized = value.casefold().strip()
    if normalized.isascii():
        return slugify(normalized)
    return _NON_WORD_RE.sub("", normalized)


def _read_concept_page(path: Path) -> tuple[dict[str, Any], str]:
    text = path.read_text(encoding="utf-8")
    if not text.startswith("---\n"):
        return {}, text
    try:
        _, remainder = text.split("---\n", 1)
        fm_text, body = remainder.split("\n---\n", 1)
    except ValueError:
        return {}, text
    try:
        frontmatter = yaml.safe_load(fm_text) or {}
    except yaml.YAMLError:
        return {}, body
    if not isinstance(frontmatter, dict):
        frontmatter = {}
    return frontmatter, body


def _canonical_name(path: Path, frontmatter: dict[str, Any], body: str) -> str:
    for key in ("concept", "title", "name"):
        value = frontmatter.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()

    for line in body.splitlines():
        if line.startswith("# "):
            heading = line[2:].strip()
            if heading:
                return heading

    return re.sub(r"[-_]+", " ", path.stem).strip() or path.stem


def _alias_values(frontmatter: dict[str, Any]) -> list[str]:
    aliases = frontmatter.get("aliases", [])
    if isinstance(aliases, str):
        aliases = [aliases]
    if not isinstance(aliases, list):
        return []
    return [alias.strip() for alias in aliases if isinstance(alias, str) and alias.strip()]


def check_concept_alias_v3(vault_path: Path, name: str) -> dict[str, Any]:
    concept_dir = vault_path / "wiki" / "concepts"
    if not concept_dir.exists():
        return {"exists": False, "canonical": name}

    query = _normalize(name)
    pages = sorted(concept_dir.glob("*.md"))

    for path in pages:
        frontmatter, body = _read_concept_page(path)
        canonical = _canonical_name(path, frontmatter, body)
        candidates = {
            _normalize(path.stem),
            _normalize(canonical),
        }
        if query in candidates:
            return {"exists": True, "canonical": canonical, "path": str(path)}

    for path in pages:
        frontmatter, body = _read_concept_page(path)
        canonical = _canonical_name(path, frontmatter, body)
        for alias in _alias_values(frontmatter):
            if query == _normalize(alias):
                return {"exists": True, "canonical": canonical, "path": str(path)}

    return {"exists": False, "canonical": name}
