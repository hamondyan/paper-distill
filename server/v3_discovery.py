from __future__ import annotations

from typing import Any

from server.config import ConfigError
from server.paper_utils import canonical_item_url
from server.v3_scoring import query_paper_sources_v3, score_papers_v3


def _paper_source_url(paper: dict[str, Any]) -> str:
    return str(
        paper.get("source_url")
        or paper.get("canonical_item_url")
        or canonical_item_url(paper)
        or ""
    ).strip()


def _paper_score(paper: dict[str, Any]) -> int:
    raw_score = paper.get("_score", 0)
    try:
        numeric = float(raw_score)
    except (TypeError, ValueError):
        return 0
    if 0 <= numeric <= 1:
        numeric *= 100
    return int(round(numeric))


def _string_list(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(item).strip() for item in value if str(item).strip()]


def _candidate_result(paper: dict[str, Any]) -> dict[str, Any] | None:
    pid = str(paper.get("paper_id", "")).strip()
    title = str(paper.get("title", "")).strip()
    if not pid or not title:
        return None

    result: dict[str, Any] = {
        "paper_id": pid,
        "title": title,
        "score": _paper_score(paper),
        "source_url": _paper_source_url(paper),
    }
    for key in ("abstract", "venue", "year", "best_topic"):
        value = paper.get(key)
        if value not in (None, ""):
            result[key] = value
    authors = _string_list(paper.get("authors"))
    if authors:
        result["authors"] = authors
    breakdown = paper.get("_score_breakdown")
    if isinstance(breakdown, dict):
        result["score_breakdown"] = breakdown
    return result


async def discover_papers_v3(query: str | None = None) -> dict[str, Any]:
    try:
        results = await query_paper_sources_v3(query=query or "", sources=None, max_results=20)
        scored_results = await score_papers_v3(results)
    except ConfigError as exc:
        return {"error": str(exc)}

    candidates = [
        candidate
        for paper in scored_results
        if (candidate := _candidate_result(paper)) is not None
    ]
    return {"results": candidates, "count": len(candidates)}
