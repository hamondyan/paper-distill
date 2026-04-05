"""Vault metadata query engine for AI agents."""
from __future__ import annotations

import glob
import logging
import os
import re
from typing import Any

import yaml

LOG = logging.getLogger(__name__)

_VAULT_SECTIONS = {
    "inbox": ["Paper Distill/inbox"],
    "raw": ["Paper Distill/raw/notes", "Paper Distill/raw"],
    "raw_source": ["Paper Distill/raw/source"],
    "raw_notes": ["Paper Distill/raw/notes"],
    "papers": ["Paper Distill/wiki/papers"],
    "concepts": ["Paper Distill/wiki/concepts"],
    "methods": ["Paper Distill/wiki/methods"],
    "topics": ["Paper Distill/wiki/topics"],
}

_FM_PATTERN = re.compile(r"\A---\s*\n(.*?)\n---", re.DOTALL)


def _parse_frontmatter(filepath: str) -> dict[str, Any] | None:
    try:
        with open(filepath, "r", encoding="utf-8") as handle:
            content = handle.read(4096)
    except (OSError, UnicodeDecodeError) as exc:
        LOG.debug("Cannot read %s: %s", filepath, exc)
        return None

    match = _FM_PATTERN.match(content)
    if not match:
        return None

    try:
        fm = yaml.safe_load(match.group(1))
    except yaml.YAMLError as exc:
        LOG.debug("Bad YAML in %s: %s", filepath, exc)
        return None

    if not isinstance(fm, dict):
        return None
    fm["_path"] = filepath
    return fm


def _iter_markdown_files(root: str, rel_paths: list[str]) -> list[str]:
    files: list[str] = []
    seen: set[str] = set()
    for rel_path in rel_paths:
        dir_path = os.path.join(root, rel_path)
        if not os.path.isdir(dir_path):
            continue
        for md_file in glob.glob(os.path.join(dir_path, "**", "*.md"), recursive=True):
            if os.path.basename(md_file) == "_index.md":
                continue
            rel_file = os.path.relpath(md_file, root)
            if rel_file.startswith("Paper Distill/raw/source") and rel_paths == _VAULT_SECTIONS["raw"]:
                continue
            if rel_file.startswith("Paper Distill/raw/notes") and md_file in seen:
                continue
            if md_file not in seen:
                seen.add(md_file)
                files.append(md_file)
    return files


def query_vault_sync(
    vault_path: str,
    section: str = "all",
    topic: str | None = None,
    uncompiled_only: bool = False,
    status: str | None = None,
) -> dict[str, Any]:
    """Walk vault directories, parse frontmatter, and return structured metadata."""
    sections = list(_VAULT_SECTIONS.keys()) if section == "all" else [section]
    result: dict[str, Any] = {"stats": {}, "sections": {}}

    for sec in sections:
        rel_paths = _VAULT_SECTIONS.get(sec)
        if not rel_paths:
            continue

        items: list[dict[str, Any]] = []
        for md_file in _iter_markdown_files(vault_path, rel_paths):
            fm = _parse_frontmatter(md_file)
            if fm is None:
                continue

            if topic:
                paper_topics = fm.get("topics", fm.get("matched_topics", []))
                if isinstance(paper_topics, str):
                    paper_topics = [paper_topics]
                if topic not in paper_topics:
                    continue

            if status and str(fm.get("status", "")).strip().lower() != status.lower():
                continue

            if uncompiled_only and fm.get("compiled") is True:
                continue

            fm["_path"] = os.path.relpath(md_file, vault_path)
            items.append(fm)

        result["stats"][sec] = len(items)
        result["sections"][sec] = items

    return result

