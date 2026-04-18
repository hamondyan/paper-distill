"""Approval helpers for inbox-native Paper Distill review."""
from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from server.paper_utils import extract_arxiv_id, normalise_title
from server.v3_bootstrap import ensure_v3_layout
from server.v3_markdown import atomic_write_text, split_frontmatter


_APPROVED_MARKER = "#approved"
_ITEM_SPLIT_RE = re.compile(r"[\n;,]+")
_ITEM_PREFIX_RE = re.compile(r"^\s*(?:[-*+]\s+|\d+[.)]\s+)")
FOLLOW_UP: list[str] = [
    "Run /ingest approved when you are ready to capture approved inbox notes.",
]


def _approved_body(body: str) -> bool:
    in_fence = False
    fence_marker = ""

    for line in body.splitlines():
        stripped = line.strip()

        if stripped.startswith(("```", "~~~")):
            marker = stripped[:3]
            if not in_fence:
                in_fence = True
                fence_marker = marker
            elif marker == fence_marker:
                in_fence = False
                fence_marker = ""
            continue

        if in_fence or not stripped or stripped.startswith(">"):
            continue

        tokens = stripped.split()
        if _APPROVED_MARKER in tokens and all(
            token.startswith("#") and len(token) > 1 for token in tokens
        ):
            return True

    return False


def _clean_item(value: str) -> str:
    cleaned = _ITEM_PREFIX_RE.sub("", value.strip())
    return cleaned.strip().strip("`").strip()


def _split_items(input_value: str) -> list[str]:
    return [
        cleaned
        for part in _ITEM_SPLIT_RE.split(input_value)
        if (cleaned := _clean_item(part))
    ]


def _read_note(path: Path) -> tuple[str, dict[str, Any], str]:
    text = path.read_text(encoding="utf-8")
    frontmatter, body, _has_frontmatter = split_frontmatter(text)
    return text, frontmatter, body


def _inbox_notes(vault_path: Path) -> list[dict[str, Any]]:
    inbox_path = vault_path / "inbox"
    if not inbox_path.exists():
        return []

    notes: list[dict[str, Any]] = []
    for note_path in sorted(inbox_path.rglob("*.md")):
        if note_path.name.startswith("_"):
            continue
        text, frontmatter, body = _read_note(note_path)
        notes.append(
            {
                "path": note_path,
                "text": text,
                "body": body,
                "paper_id": str(frontmatter.get("paper_id") or "").strip(),
                "title": str(frontmatter.get("title") or note_path.stem).strip(),
                "source_url": str(
                    frontmatter.get("source_url")
                    or frontmatter.get("canonical_html_url")
                    or ""
                ).strip(),
                "arxiv_id": str(frontmatter.get("arxiv_id") or "").strip(),
            }
        )
    return notes


def _note_summary(note: dict[str, Any]) -> dict[str, str]:
    return {
        "paper_id": str(note.get("paper_id") or ""),
        "title": str(note.get("title") or ""),
        "path": str(note.get("path") or ""),
    }


def _append_approved_marker(text: str) -> str:
    return text.rstrip() + "\n\n#approved\n"


def _item_matches_note(item: str, note: dict[str, Any], vault_path: Path) -> bool:
    note_path = Path(note["path"])
    lowered = item.casefold()
    path_values = {
        str(note_path).casefold(),
        note_path.name.casefold(),
        note_path.stem.casefold(),
    }
    try:
        path_values.add(str(note_path.relative_to(vault_path)).casefold())
    except ValueError:
        pass
    if lowered in path_values:
        return True

    paper_id = str(note.get("paper_id") or "")
    if paper_id and lowered == paper_id.casefold():
        return True

    item_arxiv_id = extract_arxiv_id(item)
    if item_arxiv_id:
        for value in (paper_id, note.get("source_url"), note.get("arxiv_id")):
            if extract_arxiv_id(str(value or "")) == item_arxiv_id:
                return True

    title = str(note.get("title") or "")
    return bool(title) and normalise_title(item) == normalise_title(title)


def _select_notes(
    vault_path: Path,
    input_value: str,
    notes: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], list[dict[str, str]]]:
    cleaned = input_value.strip()
    if cleaned.casefold() == "all":
        return notes, []

    selected: list[dict[str, Any]] = []
    errors: list[dict[str, str]] = []
    selected_paths: set[Path] = set()
    for item in _split_items(input_value):
        matches = [
            note
            for note in notes
            if _item_matches_note(item, note, vault_path)
        ]
        if not matches:
            errors.append({"input": item, "error": "No matching inbox note found."})
            continue
        for note in matches:
            note_path = Path(note["path"])
            if note_path in selected_paths:
                continue
            selected_paths.add(note_path)
            selected.append(note)
    return selected, errors


def approve_papers_v3(vault_path: Path, input_value: str) -> dict[str, Any]:
    input_value = input_value.strip()
    if not input_value:
        return {"ok": False, "error": "input_value is required", "approved": [], "errors": []}

    ensure_v3_layout(vault_path)
    notes = _inbox_notes(vault_path)
    selected, errors = _select_notes(vault_path, input_value, notes)

    approved: list[dict[str, str]] = []
    already_approved: list[dict[str, str]] = []
    for note in selected:
        if _approved_body(str(note["body"])):
            already_approved.append(_note_summary(note))
            continue
        path = Path(note["path"])
        atomic_write_text(path, _append_approved_marker(str(note["text"])))
        approved.append(_note_summary(note))

    return {
        "ok": not errors,
        "approved": approved,
        "already_approved": already_approved,
        "errors": errors,
        "approved_count": len(approved),
        "already_approved_count": len(already_approved),
        "follow_up": list(FOLLOW_UP),
    }
