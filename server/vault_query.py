"""Vault metadata query engine for AI agents."""
from __future__ import annotations

import glob
import logging
import os
from datetime import datetime, timedelta
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

def _parse_frontmatter(filepath: str) -> dict[str, Any] | None:
    try:
        with open(filepath, "r", encoding="utf-8") as handle:
            first_line = handle.readline()
            if first_line.strip() != "---":
                return None

            fm_lines: list[str] = []
            for line in handle:
                if line.strip() == "---":
                    break
                fm_lines.append(line)
            else:
                return None
    except (OSError, UnicodeDecodeError) as exc:
        LOG.debug("Cannot read %s: %s", filepath, exc)
        return None

    try:
        fm = yaml.safe_load("".join(fm_lines))
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


_COMPACT_STRIP_FIELDS = {
    "abstract", "summary", "why_recommended", "decision_note",
    "capture_error", "open_access_url",
}


def _derive_preview_text(fm: dict[str, Any]) -> str:
    """Generate a short preview from available fields (max ~25 words)."""
    tldr = str(fm.get("tldr", "") or "").strip()
    if tldr:
        return tldr
    summary = str(fm.get("summary", "") or "").strip()
    if summary:
        first_sentence = summary.split(". ")[0]
        return first_sentence[:200]
    abstract = str(fm.get("abstract", "") or "").strip()
    if abstract:
        words = abstract.split()
        return " ".join(words[:20]) + ("..." if len(words) > 20 else "")
    return ""


def _sort_key_for_item(item: dict[str, Any], sort_by: str) -> str:
    """Return a sortable string key for the given sort field."""
    if sort_by == "_mtime":
        return str(item.get("_mtime", ""))
    if sort_by == "updated_at":
        for fallback_key in (
            "updated_at",
            "retrieved_at",
            "captured_at",
            "processed_at",
            "_mtime",
        ):
            value = item.get(fallback_key)
            if value:
                return str(value)
        return ""
    return str(item.get(sort_by, "") or "")


def query_vault_sync(
    vault_path: str,
    section: str = "all",
    topic: str | None = None,
    uncompiled_only: bool = False,
    status: str | None = None,
    detail: str = "compact",
    limit: int | None = None,
    sort_by: str = "updated_at",
    days_back: int | None = None,
) -> dict[str, Any]:
    """Walk vault directories, parse frontmatter, and return structured metadata.

    Args:
        detail: "compact" strips heavy text fields and adds preview_text;
                "full" returns all frontmatter fields as-is.
        limit: Maximum number of items to return per section.
        sort_by: Field to sort by ("updated_at", "retrieved_at", "_mtime").
            When "updated_at" is requested, the query falls back to the best
            available timestamp (retrieved_at, captured_at, processed_at, then
            file mtime) if updated_at is absent.
        days_back: Only return items modified/updated within this many days.
    """
    sections = list(_VAULT_SECTIONS.keys()) if section == "all" else [section]
    result: dict[str, Any] = {"stats": {}, "sections": {}}

    cutoff_date: str | None = None
    if days_back is not None and days_back > 0:
        cutoff_date = (datetime.now() - timedelta(days=days_back)).isoformat()

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
            try:
                fm["_mtime"] = datetime.fromtimestamp(
                    os.path.getmtime(md_file)
                ).isoformat()
            except OSError:
                fm["_mtime"] = ""

            # Time-window filter
            if cutoff_date:
                sort_val = _sort_key_for_item(fm, sort_by)
                if sort_val and sort_val < cutoff_date:
                    continue

            items.append(fm)

        # Sort
        items.sort(key=lambda x: _sort_key_for_item(x, sort_by), reverse=True)

        # Limit
        if limit is not None and limit > 0:
            items = items[:limit]

        # Compact mode: strip heavy fields, add preview
        if detail == "compact":
            for item in items:
                item["preview_text"] = _derive_preview_text(item)
                for field in _COMPACT_STRIP_FIELDS:
                    item.pop(field, None)

        if sort_by != "_mtime":
            for item in items:
                item.pop("_mtime", None)

        result["stats"][sec] = len(items)
        result["sections"][sec] = items

    return result
