"""Pure v3 raw-evidence ingest helpers."""
from __future__ import annotations

import hashlib
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from server.arxiv_capture import capture_arxiv_source
from server.config import ConfigError, get_vault_path
from server.paper_utils import extract_arxiv_id, paper_id
from server.search import fetch_arxiv_record
from server.v3_bootstrap import ensure_v3_layout, paper_filename
from server.v3_markdown import split_frontmatter, write_markdown


def _read_markdown_note(path: Path) -> tuple[dict[str, Any], str]:
    text = path.read_text(encoding="utf-8")
    frontmatter, body, has_frontmatter = split_frontmatter(text)
    if not has_frontmatter:
        return {}, text.strip()
    return frontmatter, body.lstrip()


def _paper_arxiv_id(paper: dict[str, Any], source_url: str = "") -> str:
    for value in (
        paper.get("arxiv_id"),
        paper.get("paper_id"),
        source_url,
    ):
        arxiv_id = extract_arxiv_id(str(value or "").strip())
        if arxiv_id:
            return arxiv_id
    return ""


_DIRECT_ITEM_SPLIT_RE = re.compile(r"[\n;,]+")
_DIRECT_ITEM_PREFIX_RE = re.compile(r"^\s*(?:[-*+]\s+|\d+[.)]\s+)")


def _clean_direct_input_item(value: str) -> str:
    cleaned = _DIRECT_ITEM_PREFIX_RE.sub("", value.strip())
    return cleaned.strip().strip("`").strip()


def _split_direct_input_items(input_value: str) -> list[str]:
    items: list[str] = []
    for part in _DIRECT_ITEM_SPLIT_RE.split(input_value):
        cleaned = _clean_direct_input_item(part)
        if cleaned:
            items.append(cleaned)
    return items


def _existing_raw_evidence_path(vault_path: Path, paper_id_value: str) -> Path | None:
    raw_root = vault_path / "raw" / "evidence"
    if not raw_root.exists():
        return None

    for raw_path in sorted(raw_root.rglob("*.md")):
        frontmatter, _ = _read_markdown_note(raw_path)
        if str(frontmatter.get("paper_id") or "").strip() == paper_id_value:
            return raw_path
    return None


async def _capture_raw_evidence(paper: dict[str, Any], source_url: str) -> dict[str, Any]:
    arxiv_id = _paper_arxiv_id(paper, source_url)
    if not arxiv_id:
        raise ValueError("Direct URL must be an arXiv URL or arXiv DOI")

    paper = dict(paper)
    paper["arxiv_id"] = arxiv_id
    paper["paper_id"] = str(paper.get("paper_id") or paper_id(paper)).strip()
    if not paper["paper_id"]:
        paper["paper_id"] = paper_id(paper)

    captured = await capture_arxiv_source(paper)
    markdown = str(captured.markdown or "").strip()
    title = str(captured.title or paper.get("title") or paper["paper_id"]).strip()
    content_hash = hashlib.sha256(markdown.encode("utf-8")).hexdigest()
    return {
        "paper_id": paper["paper_id"],
        "title": title,
        "source_url": source_url,
        "captured_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "content_hash": content_hash,
        "markdown": markdown,
    }


def _write_raw_evidence(vault_path: Path, capture: dict[str, Any]) -> Path:
    paper_id_value = str(capture["paper_id"])
    raw_path = _existing_raw_evidence_path(vault_path, paper_id_value)
    if raw_path is None:
        raw_path = vault_path / "raw" / "evidence" / paper_filename(
            str(capture["title"]),
            paper_id_value,
        )
    frontmatter = {
        "type": "raw_evidence",
        "paper_id": paper_id_value,
        "title": capture["title"],
        "source_url": capture["source_url"],
        "captured_at": capture["captured_at"],
        "content_hash": capture["content_hash"],
    }
    write_markdown(raw_path, frontmatter, str(capture["markdown"]))
    return raw_path


_DIRECT_RESOLUTION_ERROR = "Item must be resolved to an arXiv URL, arXiv ID, or arXiv DOI before capture."
_APPROVED_WORKFLOW_RETIRED_ERROR = (
    "The legacy approval ingest workflow is retired. "
    "Pass resolved arXiv URLs, arXiv IDs, or arXiv DOI values to /ingest instead."
)


def _direct_item_error(input_item: str, error: Exception | str) -> dict[str, str]:
    message = str(error)
    return {
        "input": input_item,
        "error": message,
    }


def _direct_batch_result(
    items: list[dict[str, Any]],
    errors: list[dict[str, str]],
    skipped_duplicates: list[str],
    resolved_inputs: list[dict[str, str]],
    unresolved_inputs: list[str],
) -> dict[str, Any]:
    return {
        "items": items,
        "errors": errors,
        "captured_count": len(items),
        "error_count": len(errors),
        "skipped_duplicates": skipped_duplicates,
        "resolved_inputs": resolved_inputs,
        "unresolved_inputs": unresolved_inputs,
    }


async def ingest_and_read_v3(input_value: str) -> dict[str, Any]:
    input_value = input_value.strip()
    if not input_value:
        return {"error": "input_value is required"}

    try:
        vault_path_str = get_vault_path()
    except ConfigError as exc:
        return {"error": str(exc)}
    vault_path = Path(vault_path_str)
    ensure_v3_layout(vault_path)

    if input_value == "approved":
        return {
            "ok": False,
            "error": _APPROVED_WORKFLOW_RETIRED_ERROR,
            "items": [],
            "errors": [],
            "captured_count": 0,
            "error_count": 0,
        }

    input_items = _split_direct_input_items(input_value)
    items: list[dict[str, Any]] = []
    errors: list[dict[str, str]] = []
    skipped_duplicates: list[str] = []
    resolved_inputs: list[dict[str, str]] = []
    unresolved_inputs: list[str] = []
    seen_arxiv_ids: set[str] = set()

    for input_item in input_items:
        arxiv_id = extract_arxiv_id(input_item)
        if not arxiv_id:
            errors.append(_direct_item_error(input_item, _DIRECT_RESOLUTION_ERROR))
            unresolved_inputs.append(input_item)
            continue
        if arxiv_id in seen_arxiv_ids:
            skipped_duplicates.append(arxiv_id)
            continue
        seen_arxiv_ids.add(arxiv_id)

        source_url = input_item
        if source_url == arxiv_id:
            source_url = f"https://arxiv.org/abs/{arxiv_id}"
        resolved_inputs.append(
            {
                "input": input_item,
                "arxiv_id": arxiv_id,
                "source_url": source_url,
            }
        )

        paper = dict(await fetch_arxiv_record(arxiv_id) or {})
        paper["arxiv_id"] = str(paper.get("arxiv_id") or arxiv_id).strip()
        paper["paper_id"] = str(paper.get("paper_id") or paper_id(paper)).strip()
        if not paper["paper_id"]:
            paper["paper_id"] = paper_id(paper)
        paper["title"] = str(paper.get("title") or f"arXiv {arxiv_id}").strip()

        try:
            capture = await _capture_raw_evidence(paper, source_url)
            raw_path = _write_raw_evidence(vault_path, capture)
        except Exception as exc:
            error = {
                "input": input_item,
                "paper_id": str(paper.get("paper_id") or ""),
                "title": str(paper.get("title") or ""),
                "source_url": source_url,
                "error": str(exc),
            }
            errors.append(error)
            continue
        items.append(
            {
                "input": input_item,
                "paper_id": capture["paper_id"],
                "title": capture["title"],
                "path": str(raw_path),
                "markdown": capture["markdown"],
                "source_url": capture["source_url"],
            }
        )

    result = _direct_batch_result(
        items,
        errors,
        skipped_duplicates,
        resolved_inputs,
        unresolved_inputs,
    )
    if len(input_items) == 1 and errors and not items:
        result["error"] = errors[0]["error"]
        if "paper_id" in errors[0]:
            result["paper_id"] = errors[0].get("paper_id", "")
            result["title"] = errors[0].get("title", "")
            result["source_url"] = errors[0].get("source_url", input_items[0])
    return result
