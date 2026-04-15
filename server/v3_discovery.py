from __future__ import annotations

import json
from datetime import date
from pathlib import Path
from typing import Any

from server.config import get_vault_path
from server.paper_utils import canonical_item_url
from server.v3_bootstrap import ensure_v3_layout, paper_filename


async def search_papers(
    query: str,
    sources: list[str] | None = None,
    max_results: int = 20,
) -> list[dict[str, Any]]:
    """Local wrapper to avoid a top-level runtime import cycle."""
    from server.server_runtime import search_papers as runtime_search_papers

    return await runtime_search_papers(
        query=query,
        sources=sources,
        max_results=max_results,
    )


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
    raw_score = paper.get("score", paper.get("_score", 80))
    try:
        return int(round(float(raw_score)))
    except (TypeError, ValueError):
        return 80


def _yaml_quoted(value: str) -> str:
    return json.dumps(value, ensure_ascii=False)


def _render_inbox_stub(paper: dict[str, Any], score: int) -> str:
    title = str(paper.get("title", "")).strip() or "Untitled Paper"
    pid = str(paper.get("paper_id", "")).strip()
    source_url = _paper_source_url(paper)
    abstract = str(paper.get("abstract", "")).strip()
    body_lines = [
        f"# {title}",
        "",
        f"- Paper ID: `{pid}`",
        f"- Score: {score}",
    ]
    if source_url:
        body_lines.append(f"- Source: {source_url}")
    if abstract:
        body_lines.extend(["", abstract])
    body_lines.extend(
        [
            "",
            "Review this stub in Obsidian and mark it approved by adding the approval marker in the body when ready to ingest.",
        ]
    )
    return (
        "---\n"
        "type: inbox_stub\n"
        f"paper_id: {_yaml_quoted(pid)}\n"
        f"title: {_yaml_quoted(title)}\n"
        f"source_url: {_yaml_quoted(source_url)}\n"
        f'discovered_at: "{date.today().isoformat()}"\n'
        f"score: {score}\n"
        "---\n\n"
        + "\n".join(body_lines)
        + "\n"
    )


async def discover_papers_v3(query: str | None = None) -> dict[str, Any]:
    vault_path = Path(get_vault_path())
    ensure_v3_layout(vault_path)
    cache = _load_seen_cache(vault_path)
    results = await search_papers(query=query or "", sources=None, max_results=20)

    saved: list[dict[str, Any]] = []
    skipped_seen: list[str] = []
    discovered_on = date.today().isoformat()

    for paper in results:
        pid = str(paper.get("paper_id", "")).strip()
        title = str(paper.get("title", "")).strip()
        if not pid or not title:
            continue
        if pid in cache:
            skipped_seen.append(pid)
            continue

        score = _paper_score(paper)
        inbox_path = vault_path / "inbox" / paper_filename(title, pid)
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
