from __future__ import annotations

import json
from datetime import date
from pathlib import Path
from typing import Any

from server.config import ConfigError, get_vault_path
from server.paper_utils import canonical_item_url
from server.v3_bootstrap import ensure_v3_layout, paper_filename
from server.v3_scoring import query_paper_sources_v3, score_papers_v3


def _load_seen_cache(vault_path: Path) -> dict[str, dict[str, Any]]:
    cache_path = vault_path / ".state" / "seen_papers.json"
    payload = json.loads(cache_path.read_text(encoding="utf-8"))
    return payload if isinstance(payload, dict) else {}


def _write_seen_cache(vault_path: Path, payload: dict[str, dict[str, Any]]) -> None:
    cache_path = vault_path / ".state" / "seen_papers.json"
    cache_path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def _paper_source_url(paper: dict[str, Any]) -> str:
    return str(
        paper.get("source_url")
        or paper.get("canonical_item_url")
        or canonical_item_url(paper)
        or ""
    ).strip()


def _paper_score(paper: dict[str, Any]) -> int:
    raw_score = paper.get("_score", 80)
    try:
        return int(round(float(raw_score)))
    except (TypeError, ValueError):
        return 80


def _sanitize_stub_text(value: str) -> str:
    return value.replace("#approved", "# approved")


def _inbox_note_paper_id(text: str) -> str:
    if not text.startswith("---\n"):
        return ""
    try:
        frontmatter_text = text.split("---\n", 1)[1].split("\n---\n", 1)[0]
    except ValueError:
        return ""
    for line in frontmatter_text.splitlines():
        if line.startswith("paper_id:"):
            return line.split(":", 1)[1].strip().strip("'\"")
    return ""


def _inbox_note_body(text: str) -> str:
    if "\n---\n\n" not in text:
        return ""
    try:
        return text.split("\n---\n\n", 1)[1]
    except IndexError:
        return ""


def _existing_approved_inbox_note(vault_path: Path, paper_id: str) -> Path | None:
    inbox_path = vault_path / "inbox"
    if not inbox_path.exists():
        return None
    for note_path in sorted(inbox_path.rglob("*.md")):
        try:
            text = note_path.read_text(encoding="utf-8")
        except OSError:
            continue
        if "#approved" not in _inbox_note_body(text):
            continue
        if _inbox_note_paper_id(text) == paper_id:
            return note_path
    return None


def _yaml_quoted(value: str) -> str:
    return json.dumps(value, ensure_ascii=False)


def _render_inbox_stub(paper: dict[str, Any], score: int) -> str:
    raw_title = str(paper.get("title", "")).strip() or "Untitled Paper"
    pid = str(paper.get("paper_id", "")).strip()
    raw_source_url = _paper_source_url(paper)
    body_title = _sanitize_stub_text(raw_title)
    body_source_url = _sanitize_stub_text(raw_source_url)
    body_abstract = _sanitize_stub_text(str(paper.get("abstract", "")).strip())
    body_lines = [
        f"# {body_title}",
        "",
        f"- Paper ID: `{pid}`",
        f"- Score: {score}",
    ]
    if body_source_url:
        body_lines.append(f"- Source: {body_source_url}")
    if body_abstract:
        body_lines.extend(["", body_abstract])
    body_lines.extend(
        [
            "",
            "Review this stub in Obsidian before ingesting.",
        ]
    )
    return (
        "---\n"
        "type: inbox_stub\n"
        f"paper_id: {_yaml_quoted(pid)}\n"
        f"title: {_yaml_quoted(raw_title)}\n"
        f"source_url: {_yaml_quoted(raw_source_url)}\n"
        f'discovered_at: "{date.today().isoformat()}"\n'
        f"score: {score}\n"
        "---\n\n"
        + "\n".join(body_lines)
        + "\n"
    )


async def discover_papers_v3(query: str | None = None) -> dict[str, Any]:
    try:
        vault_path = Path(get_vault_path())
    except ConfigError as exc:
        return {"error": str(exc)}
    ensure_v3_layout(vault_path)
    cache = _load_seen_cache(vault_path)
    results = await query_paper_sources_v3(query=query or "", sources=None, max_results=20)
    scored_results = await score_papers_v3(results)

    saved: list[dict[str, Any]] = []
    skipped_seen: list[str] = []
    discovered_on = date.today().isoformat()

    for paper in scored_results:
        pid = str(paper.get("paper_id", "")).strip()
        title = str(paper.get("title", "")).strip()
        if not pid or not title:
            continue
        if pid in cache:
            skipped_seen.append(pid)
            continue
        if _existing_approved_inbox_note(vault_path, pid):
            skipped_seen.append(pid)
            continue

        score = _paper_score(paper)
        inbox_path = vault_path / "inbox" / paper_filename(title, pid)
        if inbox_path.exists():
            skipped_seen.append(pid)
            continue
        inbox_path.write_text(_render_inbox_stub(paper, score), encoding="utf-8")

        cache[pid] = {
            "title": title,
            "score": score,
            "source_url": _paper_source_url(paper),
            "added_at": discovered_on,
        }
        saved.append(
            {
                "paper_id": pid,
                "path": str(inbox_path),
                "score": score,
            }
        )

    _write_seen_cache(vault_path, cache)
    return {"saved": saved, "skipped_seen": skipped_seen}
