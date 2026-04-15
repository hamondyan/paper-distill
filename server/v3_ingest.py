"""Pure v3 raw-evidence ingest helpers."""
from __future__ import annotations

import hashlib
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yaml

from server.arxiv_capture import capture_arxiv_source
from server.config import get_vault_path
from server.paper_utils import extract_arxiv_id, paper_id
from server.search import fetch_arxiv_record
from server.v3_bootstrap import ensure_v3_layout, paper_filename
from server.vault_ops import write_markdown

_APPROVED_MARKER = "#approved"


def _read_markdown_note(path: Path) -> tuple[dict[str, Any], str]:
    text = path.read_text(encoding="utf-8")
    if not text.startswith("---\n"):
        return {}, text.strip()
    try:
        _, remainder = text.split("---\n", 1)
        fm_text, body = remainder.split("\n---\n", 1)
    except ValueError:
        return {}, text.strip()
    frontmatter = yaml.safe_load(fm_text) or {}
    if not isinstance(frontmatter, dict):
        frontmatter = {}
    return frontmatter, body.lstrip()


def _approved_body(body: str) -> bool:
    return _APPROVED_MARKER in body


def _approved_inbox_papers(vault_path: Path) -> list[dict[str, Any]]:
    inbox_root = vault_path / "inbox"
    if not inbox_root.exists():
        return []

    papers: list[dict[str, Any]] = []
    for note_path in sorted(inbox_root.rglob("*.md")):
        if note_path.name.startswith("_"):
            continue

        frontmatter, body = _read_markdown_note(note_path)
        if not _approved_body(body):
            continue

        paper = dict(frontmatter)
        source_url = str(
            frontmatter.get("source_url")
            or frontmatter.get("canonical_html_url")
            or ""
        ).strip()
        if not source_url:
            arxiv_id = str(frontmatter.get("arxiv_id") or "").strip()
            if arxiv_id:
                source_url = f"https://arxiv.org/abs/{arxiv_id}"

        paper["source_url"] = source_url
        paper["arxiv_id"] = str(frontmatter.get("arxiv_id") or extract_arxiv_id(source_url) or "").strip()
        paper["paper_id"] = str(frontmatter.get("paper_id") or "").strip()
        if not paper["paper_id"]:
            paper["paper_id"] = paper_id(paper)
        paper["title"] = str(frontmatter.get("title") or paper.get("title") or paper["paper_id"]).strip()
        paper["_note_path"] = str(note_path)
        papers.append(paper)

    return papers


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
    arxiv_id = str(paper.get("arxiv_id") or extract_arxiv_id(source_url) or "").strip()
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


async def ingest_and_read_v3(input_value: str) -> dict[str, Any]:
    input_value = input_value.strip()
    if not input_value:
        return {"error": "input_value is required"}

    vault_path_str = get_vault_path()
    if not vault_path_str:
        return {"error": "VAULT_PATH not configured."}

    vault_path = Path(vault_path_str)
    ensure_v3_layout(vault_path)

    if input_value == "approved":
        items: list[dict[str, Any]] = []
        for paper in _approved_inbox_papers(vault_path):
            source_url = str(paper.get("source_url") or "").strip()
            if not source_url:
                continue
            capture = await _capture_raw_evidence(paper, source_url)
            raw_path = _write_raw_evidence(vault_path, capture)
            items.append(
                {
                    "paper_id": capture["paper_id"],
                    "title": capture["title"],
                    "path": str(raw_path),
                    "markdown": capture["markdown"],
                    "source_url": capture["source_url"],
                }
            )
        return {"items": items}

    source_url = input_value
    arxiv_id = extract_arxiv_id(source_url)
    if not arxiv_id:
        return {"error": "Direct URL must be an arXiv URL or arXiv DOI"}

    paper = dict(await fetch_arxiv_record(arxiv_id) or {})
    paper["arxiv_id"] = str(paper.get("arxiv_id") or arxiv_id).strip()
    paper["paper_id"] = str(paper.get("paper_id") or paper_id(paper)).strip()
    if not paper["paper_id"]:
        paper["paper_id"] = paper_id(paper)
    paper["title"] = str(paper.get("title") or f"arXiv {arxiv_id}").strip()

    capture = await _capture_raw_evidence(paper, source_url)
    raw_path = _write_raw_evidence(vault_path, capture)
    return {
        "items": [
            {
                "paper_id": capture["paper_id"],
                "title": capture["title"],
                "path": str(raw_path),
                "markdown": capture["markdown"],
                "source_url": capture["source_url"],
            }
        ]
    }
