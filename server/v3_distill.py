"""High-level paper distillation workflow helpers."""
from __future__ import annotations

from pathlib import Path
from typing import Any

from server.v3_bootstrap import paper_filename
from server.v3_markdown import split_frontmatter
from server.v3_store import upsert_wiki_page_v3


def _normalize_lookup(value: str) -> str:
    text = value.casefold().strip()
    for prefix in ("https://arxiv.org/abs/", "http://arxiv.org/abs/", "10.48550/arxiv.", "arxiv:"):
        if text.startswith(prefix):
            text = text[len(prefix) :]
            break
    return text.strip()


def _raw_evidence_files(vault_path: Path) -> list[Path]:
    evidence_dir = vault_path / "raw" / "evidence"
    if not evidence_dir.is_dir():
        return []
    return sorted(evidence_dir.glob("*.md"))


def _is_raw_evidence_path(vault_path: Path, input_value: str) -> Path | None:
    candidate = Path(input_value).expanduser()
    if not candidate.is_absolute():
        candidate = vault_path / candidate
    if not candidate.exists() or candidate.suffix != ".md":
        return None
    try:
        candidate_resolved = candidate.resolve()
        evidence_root = (vault_path / "raw" / "evidence").resolve()
        candidate_resolved.relative_to(evidence_root)
    except (OSError, ValueError):
        return None
    return candidate


def _read_evidence_metadata(path: Path) -> tuple[dict[str, Any], str]:
    text = path.read_text(encoding="utf-8")
    frontmatter, body, _ = split_frontmatter(text)
    return frontmatter, body


def _resolve_raw_evidence(vault_path: Path, input_value: str) -> dict[str, Any]:
    raw_input = input_value.strip()
    if not raw_input:
        return {"ok": False, "error": "input_value is required", "candidates": []}

    path_input = _is_raw_evidence_path(vault_path, raw_input)
    if path_input is not None:
        frontmatter, body = _read_evidence_metadata(path_input)
        return {"ok": True, "path": path_input, "frontmatter": frontmatter, "body": body}

    lookup = _normalize_lookup(raw_input)
    matches: list[dict[str, Any]] = []
    for path in _raw_evidence_files(vault_path):
        frontmatter, body = _read_evidence_metadata(path)
        paper_id = str(frontmatter.get("paper_id") or "").strip()
        title = str(frontmatter.get("title") or "").strip()
        searchable = {
            _normalize_lookup(paper_id),
            path.stem.casefold(),
            title.casefold(),
        }
        if lookup in searchable or (lookup and lookup in title.casefold()):
            matches.append(
                {
                    "path": path,
                    "frontmatter": frontmatter,
                    "body": body,
                    "paper_id": paper_id,
                    "title": title,
                }
            )

    if not matches:
        return {
            "ok": False,
            "error": f"raw evidence not found for input: {input_value}",
            "candidates": [],
        }
    if len(matches) > 1:
        return {
            "ok": False,
            "error": f"ambiguous raw evidence input: {input_value}",
            "candidates": [
                {
                    "paper_id": match.get("paper_id", ""),
                    "title": match.get("title", ""),
                    "path": str(match["path"]),
                }
                for match in matches
            ],
        }
    match = matches[0]
    return {
        "ok": True,
        "path": match["path"],
        "frontmatter": match["frontmatter"],
        "body": match["body"],
    }


def _target_from_payload(
    distilled: dict[str, Any],
    evidence_frontmatter: dict[str, Any],
) -> str:
    target = str(distilled.get("target") or "").strip()
    if target:
        return target.removesuffix(".md")
    frontmatter = distilled.get("frontmatter")
    if not isinstance(frontmatter, dict):
        frontmatter = {}
    title = str(frontmatter.get("title") or evidence_frontmatter.get("title") or "").strip()
    paper_id = str(frontmatter.get("paper_id") or evidence_frontmatter.get("paper_id") or "").strip()
    return paper_filename(title or "Untitled Paper", paper_id or "unknown").removesuffix(".md")


def _payload_or_error(distilled: dict[str, Any] | None) -> dict[str, Any] | None:
    if distilled is None:
        return None
    if not isinstance(distilled, dict):
        return {"ok": False, "error": "distilled must be an object", "warnings": []}
    if not isinstance(distilled.get("frontmatter"), dict):
        return {"ok": False, "error": "distilled.frontmatter is required", "warnings": []}
    if not isinstance(distilled.get("body"), str) or not distilled["body"].strip():
        return {"ok": False, "error": "distilled.body is required", "warnings": []}
    return None


def distill_paper_v3(
    vault_path: Path,
    input_value: str,
    distilled: dict[str, Any] | None = None,
) -> dict[str, Any]:
    resolved = _resolve_raw_evidence(vault_path, input_value)
    if not resolved["ok"]:
        return resolved

    evidence_path: Path = resolved["path"]
    evidence_frontmatter: dict[str, Any] = resolved["frontmatter"]
    paper_id = str(evidence_frontmatter.get("paper_id") or "").strip()

    payload_error = _payload_or_error(distilled)
    if distilled is None:
        return {
            "ok": False,
            "status": "needs_distillation_payload",
            "paper_id": paper_id,
            "raw_evidence_path": str(evidence_path),
            "message": "Read raw evidence, then call again with distilled.frontmatter and distilled.body.",
        }
    if payload_error is not None:
        return payload_error

    target = _target_from_payload(distilled, evidence_frontmatter)
    frontmatter = dict(distilled["frontmatter"])
    if paper_id and not frontmatter.get("paper_id"):
        frontmatter["paper_id"] = paper_id
    if evidence_frontmatter.get("title") and not frontmatter.get("title"):
        frontmatter["title"] = evidence_frontmatter["title"]

    result = upsert_wiki_page_v3(
        vault_path,
        "paper",
        target,
        frontmatter,
        distilled["body"],
    )
    if result.get("ok"):
        result["raw_evidence_path"] = str(evidence_path)
    return result


def distill_papers_v3(
    vault_path: Path,
    items: list[dict[str, Any]],
) -> dict[str, Any]:
    results: list[dict[str, Any]] = []
    for item in items:
        if not isinstance(item, dict):
            results.append({"ok": False, "error": "each item must be an object"})
            continue
        results.append(
            distill_paper_v3(
                vault_path,
                str(item.get("input_value") or ""),
                item.get("distilled"),
            )
        )
    return {"ok": all(result.get("ok") for result in results), "results": results}
