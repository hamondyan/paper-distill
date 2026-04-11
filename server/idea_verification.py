"""Idea-note-first verification writer.

The default idea flow now writes a single human-editable note under
``insights/ideas``. Verification state, blockers, contradictions, and follow-up
guidance all live inside that note. No auxiliary snapshot JSON or memory
follow-up is produced on this path.
"""
from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

import yaml

from server.database import _now_iso
from server.vault_contract import root_path
from server.vault_ops import ensure_vault_structure, write_markdown

_SCHEMA_VERSION = "2026-04-10"
_IDEA_ID_RE = re.compile(r"^[a-z0-9][a-z0-9_-]*$")
_LAYER_ORDER = ("wiki", "sources", "memory")
_PROVIDER_STATUSES = {"succeeded", "failed", "partial", "contradicted"}
_MAX_PROVIDER_EVIDENCE = 5
_MAX_EXCERPT_CHARS = 400
_DEFAULT_WORKING_NOTES = "- Add personal notes, links, or decisions here."


class IdeaVerificationValidationError(ValueError):
    """Raised when an idea verification request is structurally invalid."""


class VerificationProviderError(RuntimeError):
    """Named provider failure for callers that live-hit external verification."""


def verify_idea(
    vault_path: str,
    *,
    idea: dict[str, Any],
    verification: dict[str, Any],
) -> dict[str, Any]:
    """Write or refresh a single idea note without runtime snapshots."""
    candidate_idea_id = _candidate_idea_id(idea)
    try:
        normalized_idea = _normalize_idea_request(idea)
        normalized_verification = _normalize_verification_request(verification)
    except IdeaVerificationValidationError as exc:
        return _failure_result(
            idea_id=candidate_idea_id,
            error=str(exc),
            verification_state="unknown",
        )

    return _persist_idea_note(
        vault_path,
        idea=normalized_idea,
        verification=normalized_verification,
    )


def _persist_idea_note(
    vault_path: str,
    *,
    idea: dict[str, Any],
    verification: dict[str, Any],
) -> dict[str, Any]:
    ensure_vault_structure(vault_path)
    now = _now_iso()
    note_path = _idea_note_path(vault_path, idea["idea_id"])
    existing_frontmatter, working_notes = _read_existing_note(note_path)

    verification_state = verification["verification_state"]
    idea_state = _idea_state_for_verification_state(verification_state)
    decision_reason = _decision_reason_for_verification_state(verification_state)
    decision_at = now if decision_reason else ""
    related = _collect_related_refs(idea)
    topics = _merge_string_lists(existing_frontmatter.get("topics"), idea.get("topics"))
    similar_existing_ideas = _find_similar_existing_ideas(
        vault_path,
        idea_id=idea["idea_id"],
        title=idea["title"],
    )

    frontmatter = _build_note_frontmatter(
        idea=idea,
        verification=verification,
        existing_frontmatter=existing_frontmatter,
        idea_state=idea_state,
        decision_reason=decision_reason,
        decision_at=decision_at,
        updated_at=now,
        topics=topics,
        related=related,
        similar_existing_ideas=similar_existing_ideas,
    )
    body = _build_note_body(
        idea=idea,
        verification=verification,
        idea_state=idea_state,
        decision_reason=decision_reason,
        working_notes=working_notes,
        similar_existing_ideas=similar_existing_ideas,
    )

    try:
        write_markdown(note_path, frontmatter, body)
    except OSError as exc:
        return _failure_result(
            idea_id=idea["idea_id"],
            error=f"Failed to write idea note {idea['idea_id']}: {exc}",
            verification_state=verification_state,
            idea_path=str(note_path),
        )

    return _success_result(
        idea_id=idea["idea_id"],
        idea_path=str(note_path),
        verification_state=verification_state,
        idea_state=idea_state,
        decision_reason=decision_reason,
        decision_at=decision_at,
        provider_summary=verification["provider_summary"],
        missing_providers=verification["missing_providers"],
        similar_existing_ideas=similar_existing_ideas,
    )


def _success_result(
    *,
    idea_id: str,
    idea_path: str,
    verification_state: str,
    idea_state: str,
    decision_reason: str,
    decision_at: str,
    provider_summary: dict[str, Any],
    missing_providers: list[str],
    similar_existing_ideas: list[str],
) -> dict[str, Any]:
    is_verified = verification_state == "verified"
    return {
        "ok": True,
        "idea_id": idea_id,
        "idea_path": idea_path,
        "idea_write_state": "saved",
        "note_write_state": "saved",
        "idea_state": idea_state,
        "verification_state": verification_state,
        "verified": is_verified,
        "decision_reason": decision_reason,
        "decision_at": decision_at,
        "provider_summary": provider_summary,
        "missing_providers": missing_providers,
        "similar_existing_ideas": similar_existing_ideas,
        "promoted": is_verified,
        "promotion_blocked": not is_verified,
        "promotion_block_reason": decision_reason or None,
        "snapshot_persisted": False,
        "snapshot_write_state": "disabled",
        "snapshot_path": None,
        "snapshot_id": None,
        "killed_ideas_memory_state": "skipped",
        "killed_ideas_memory_error": None,
    }


def _failure_result(
    *,
    idea_id: str | None,
    error: str,
    verification_state: str,
    idea_path: str | None = None,
) -> dict[str, Any]:
    return {
        "ok": False,
        "idea_id": idea_id,
        "idea_path": idea_path,
        "idea_write_state": "failed",
        "note_write_state": "failed",
        "idea_state": "unchanged",
        "verification_state": verification_state,
        "verified": False,
        "decision_reason": "",
        "decision_at": "",
        "provider_summary": {},
        "missing_providers": [],
        "similar_existing_ideas": [],
        "promoted": False,
        "promotion_blocked": True,
        "promotion_block_reason": None,
        "snapshot_persisted": False,
        "snapshot_write_state": "disabled",
        "snapshot_path": None,
        "snapshot_id": None,
        "killed_ideas_memory_state": "skipped",
        "killed_ideas_memory_error": None,
        "error": error,
    }


def _build_note_frontmatter(
    *,
    idea: dict[str, Any],
    verification: dict[str, Any],
    existing_frontmatter: dict[str, Any],
    idea_state: str,
    decision_reason: str,
    decision_at: str,
    updated_at: str,
    topics: list[str],
    related: dict[str, list[str]],
    similar_existing_ideas: list[str],
) -> dict[str, Any]:
    provider_summary = verification["provider_summary"]
    return {
        "schema_version": _SCHEMA_VERSION,
        "type": "idea-note",
        "section": "insights/ideas",
        "idea_id": idea["idea_id"],
        "title": idea["title"],
        "date": updated_at.split("T", 1)[0],
        "updated": updated_at,
        "status": "saved",
        "idea_state": idea_state,
        "verification_state": verification["verification_state"],
        "verified": verification["verification_state"] == "verified",
        "decision_reason": decision_reason,
        "decision_at": decision_at,
        "superseded_by": str(
            idea.get("superseded_by")
            or existing_frontmatter.get("superseded_by")
            or ""
        ).strip(),
        "topics": topics,
        "related_papers": _merge_string_lists(
            existing_frontmatter.get("related_papers"),
            related["papers"],
        ),
        "related_concepts": _merge_string_lists(
            existing_frontmatter.get("related_concepts"),
            related["concepts"],
        ),
        "required_providers": list(verification["required_providers"]),
        "missing_providers": list(verification["missing_providers"]),
        "providers_succeeded": list(provider_summary.get("succeeded") or []),
        "providers_failed": list(provider_summary.get("failed") or []),
        "providers_partial": list(provider_summary.get("partial") or []),
        "providers_contradicted": list(provider_summary.get("contradicted") or []),
        "similar_existing_ideas": similar_existing_ideas,
    }


def _build_note_body(
    *,
    idea: dict[str, Any],
    verification: dict[str, Any],
    idea_state: str,
    decision_reason: str,
    working_notes: str,
    similar_existing_ideas: list[str],
) -> str:
    lines = [
        f"# {idea['title']}",
        "",
        "## Summary",
        "",
        idea["summary"],
        "",
        "## Local Evidence",
        "",
        "Trust order stays fixed: wiki, sources, memory, then external checks.",
    ]

    for layer in _LAYER_ORDER:
        lines.extend(["", f"### {layer.title()}", ""])
        entries = idea["local_evidence"].get(layer) or []
        if not entries:
            lines.append("- None captured.")
            continue
        for item in entries:
            lines.append(f"- {_format_evidence_item(item)}")

    lines.extend(["", "### External Checks", ""])
    lines.extend(_external_check_lines(verification))

    if similar_existing_ideas:
        lines.extend(["", "### Similar Existing Ideas", ""])
        for ref in similar_existing_ideas:
            lines.append(f"- {ref}")

    lines.extend(
        [
            "",
            "## Hypothesis / Bridge",
            "",
            idea["hypothesis"] or "- To be clarified.",
            "",
            "## Kill Criteria",
            "",
        ]
    )
    lines.extend(_kill_criteria_lines(verification, idea_state=idea_state))
    lines.extend(
        [
            "",
            "## Next Step",
            "",
            _next_step_text(verification["verification_state"]),
        ]
    )

    if decision_reason:
        lines.extend(
            [
                "",
                "## Decision Notes",
                "",
                f"- Current state: {idea_state}",
                f"- Decision reason: {decision_reason}",
            ]
        )

    lines.extend(
        [
            "",
            "## Working Notes",
            "",
            working_notes or _DEFAULT_WORKING_NOTES,
        ]
    )
    return "\n".join(lines).strip()


def _external_check_lines(verification: dict[str, Any]) -> list[str]:
    provider_summary = verification["provider_summary"]
    lines = [
        f"- Verification state: {verification['verification_state']}",
        f"- Required providers: {', '.join(verification['required_providers']) or 'none'}",
        f"- Missing providers: {', '.join(verification['missing_providers']) or 'none'}",
        f"- Providers succeeded: {', '.join(provider_summary.get('succeeded') or []) or 'none'}",
        f"- Providers failed: {', '.join(provider_summary.get('failed') or []) or 'none'}",
        f"- Providers partial: {', '.join(provider_summary.get('partial') or []) or 'none'}",
        f"- Providers contradicted: {', '.join(provider_summary.get('contradicted') or []) or 'none'}",
    ]

    for provider in verification["providers"]:
        details = [provider["status"]]
        if provider.get("query"):
            details.append(provider["query"])
        if provider.get("error"):
            details.append(f"error={provider['error']}")
        lines.append(f"- Provider {provider['provider']}: {' | '.join(details)}")
        for item in provider.get("evidence") or []:
            lines.append(f"- Evidence [{provider['provider']}]: {_format_provider_evidence(item)}")

    contradictions = verification["contradictions"]
    if contradictions:
        lines.append("- Contradictions:")
        for item in contradictions:
            lines.append(f"- {_format_evidence_item(item)}")

    notes = verification["notes"]
    if notes:
        lines.append(f"- Verification notes: {notes}")
    return lines


def _kill_criteria_lines(verification: dict[str, Any], *, idea_state: str) -> list[str]:
    contradictions = verification["contradictions"]
    provider_summary = verification["provider_summary"]
    missing_providers = verification["missing_providers"]
    verification_state = verification["verification_state"]

    if contradictions:
        lines = [f"- {_format_evidence_item(item)}" for item in contradictions]
        lines.append("- Reject this idea while the contradiction still holds.")
        return lines

    if verification_state == "provider_failed":
        lines = [
            "- External verification is incomplete because at least one required provider failed.",
        ]
        if provider_summary.get("failed"):
            lines.append(
                f"- Failed providers: {', '.join(provider_summary.get('failed') or [])}"
            )
        return lines

    if verification_state == "partial":
        lines = [
            "- This idea stays parked until the missing providers complete their checks.",
        ]
        if missing_providers:
            lines.append(f"- Missing providers: {', '.join(missing_providers)}")
        return lines

    if idea_state == "active":
        return [
            "- Invalidate this idea if stronger local or external evidence shows the core bridge is already solved, infeasible, or based on a false premise.",
        ]

    return ["- Re-evaluate this idea if the decision context materially changes."]


def _next_step_text(verification_state: str) -> str:
    if verification_state == "contradicted":
        return "Only reopen if the contradiction is resolved or the core assumptions materially change."
    if verification_state == "provider_failed":
        return "Collect a clean pass from the failed or missing providers, then revisit the idea note."
    if verification_state == "partial":
        return "Re-run verification after the missing providers complete their checks or the local evidence becomes stronger."
    return "Search for adjacent papers, decide whether this should become a topic or concept thread, and add an execution sketch in Working Notes."


def _read_existing_note(path: Path) -> tuple[dict[str, Any], str]:
    if not path.exists():
        return {}, ""

    try:
        content = path.read_text(encoding="utf-8")
    except OSError:
        return {}, ""
    if not content.startswith("---\n"):
        return {}, ""
    try:
        _, remainder = content.split("---\n", 1)
        fm_text, body = remainder.split("\n---\n", 1)
        decoded = yaml.safe_load(fm_text) or {}
        frontmatter = decoded if isinstance(decoded, dict) else {}
    except ValueError:
        return {}, ""
    return frontmatter, _extract_working_notes(body)


def _extract_working_notes(body: str) -> str:
    marker = "\n## Working Notes\n"
    if marker not in body:
        return ""
    _, remainder = body.split(marker, 1)
    return remainder.strip()


def _idea_note_path(vault_path: str, idea_id: str) -> Path:
    return root_path(vault_path, "ideas") / f"{idea_id}.md"


def _find_similar_existing_ideas(vault_path: str, *, idea_id: str, title: str) -> list[str]:
    ideas_root = root_path(vault_path, "ideas")
    if not ideas_root.exists():
        return []

    title_tokens = _title_tokens(title)
    similar: list[str] = []
    for path in sorted(ideas_root.glob("*.md")):
        if path.stem == idea_id:
            continue
        other_title = _title_for_existing_note(path)
        if not other_title:
            continue
        score = _title_similarity(title_tokens, _title_tokens(other_title))
        if score >= 0.4:
            similar.append(_paper_distill_ref(vault_path, path))
    return similar[:5]


def _title_for_existing_note(path: Path) -> str:
    frontmatter, _ = _read_existing_note(path)
    title = str(frontmatter.get("title") or "").strip()
    if title:
        return title
    return path.stem.replace("-", " ")


def _title_tokens(text: str) -> set[str]:
    return {token for token in re.split(r"[^a-z0-9]+", text.lower()) if len(token) >= 4}


def _title_similarity(left: set[str], right: set[str]) -> float:
    if not left or not right:
        return 0.0
    overlap = left & right
    return len(overlap) / max(len(left), len(right))


def _paper_distill_ref(vault_path: str, path: Path) -> str:
    root = Path(vault_path).expanduser() / "Paper Distill"
    return f"Paper Distill/{path.relative_to(root).as_posix()}"


def _collect_related_refs(idea: dict[str, Any]) -> dict[str, list[str]]:
    related = {
        "papers": [],
        "concepts": [],
    }
    for layer in _LAYER_ORDER:
        for item in idea["local_evidence"].get(layer) or []:
            ref = str(item.get("ref") or "").strip()
            if ref.startswith("Paper Distill/wiki/papers/"):
                related["papers"].append(ref)
            elif ref.startswith("Paper Distill/wiki/concepts/"):
                related["concepts"].append(ref)
    return {
        key: _merge_string_lists(values)
        for key, values in related.items()
    }


def _merge_string_lists(*sources: Any) -> list[str]:
    merged: list[str] = []
    seen: set[str] = set()
    for source in sources:
        if source is None:
            continue
        if isinstance(source, str):
            items = [source]
        else:
            items = list(source)
        for raw_item in items:
            item = str(raw_item or "").strip()
            if not item or item in seen:
                continue
            seen.add(item)
            merged.append(item)
    return merged


def _idea_state_for_verification_state(verification_state: str) -> str:
    if verification_state == "verified":
        return "active"
    if verification_state == "contradicted":
        return "rejected"
    if verification_state in {"provider_failed", "partial"}:
        return "parked"
    return "active"


def _decision_reason_for_verification_state(verification_state: str) -> str:
    if verification_state == "provider_failed":
        return "provider_failed"
    if verification_state == "partial":
        return "partial_evidence"
    if verification_state == "contradicted":
        return "contradiction_detected"
    return ""


def _format_provider_evidence(item: dict[str, str]) -> str:
    parts = [
        item.get("title") or "",
        item.get("stance") or "",
        item.get("excerpt") or item.get("url") or "",
    ]
    return " - ".join(part for part in parts if part).strip() or "evidence"


def _format_evidence_item(item: dict[str, str]) -> str:
    label = item.get("ref") or item.get("title") or item.get("view_key") or "evidence"
    extras = [item.get("summary") or "", item.get("excerpt") or ""]
    detail = " ".join(part for part in extras if part).strip()
    if detail:
        return f"{label} - {detail}"
    return str(label)


def _normalize_idea_request(idea: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(idea, dict):
        raise IdeaVerificationValidationError("Idea payload must be an object.")

    idea_id = str(idea.get("idea_id") or "").strip()
    if not idea_id:
        raise IdeaVerificationValidationError("Idea payload requires non-empty idea_id.")
    if not _IDEA_ID_RE.match(idea_id):
        raise IdeaVerificationValidationError(f"Invalid idea_id: {idea_id}")

    title = str(idea.get("title") or "").strip()
    if not title:
        raise IdeaVerificationValidationError("Idea payload requires non-empty title.")

    summary = str(idea.get("summary") or "").strip()
    if not summary:
        raise IdeaVerificationValidationError("Idea payload requires non-empty summary.")

    local_evidence_payload = idea.get("local_evidence") or {}
    if not isinstance(local_evidence_payload, dict):
        raise IdeaVerificationValidationError("Idea local_evidence must be an object.")

    local_evidence: dict[str, list[dict[str, str]]] = {}
    for layer in _LAYER_ORDER:
        local_evidence[layer] = _normalize_evidence_items(local_evidence_payload.get(layer))

    return {
        "idea_id": idea_id,
        "title": title,
        "summary": summary,
        "hypothesis": str(idea.get("hypothesis") or "").strip(),
        "topics": _merge_string_lists(idea.get("topics")),
        "superseded_by": str(idea.get("superseded_by") or "").strip(),
        "local_evidence": local_evidence,
    }


def _normalize_verification_request(verification: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(verification, dict):
        raise IdeaVerificationValidationError("Verification payload must be an object.")

    queries = _normalize_string_list(
        verification.get("queries")
        if verification.get("queries") is not None
        else ([verification.get("query")] if verification.get("query") is not None else None)
    )
    providers = _normalize_provider_results(verification.get("providers"))
    required_providers = _normalize_string_list(verification.get("required_providers"))
    if not required_providers:
        required_providers = [provider["provider"] for provider in providers]

    if not providers and not required_providers:
        raise IdeaVerificationValidationError(
            "Verification payload requires providers or required_providers."
        )

    contradictions = _normalize_evidence_items(verification.get("contradictions"))
    provider_names = [provider["provider"] for provider in providers]
    missing_providers = [name for name in required_providers if name not in provider_names]
    provider_summary = {
        "attempted": provider_names,
        "succeeded": [provider["provider"] for provider in providers if provider["status"] == "succeeded"],
        "failed": [provider["provider"] for provider in providers if provider["status"] == "failed"],
        "partial": [provider["provider"] for provider in providers if provider["status"] == "partial"],
        "contradicted": [provider["provider"] for provider in providers if provider["status"] == "contradicted"],
    }

    if contradictions or provider_summary["contradicted"]:
        verification_state = "contradicted"
    elif provider_summary["failed"]:
        verification_state = "provider_failed"
    elif missing_providers or provider_summary["partial"]:
        verification_state = "partial"
    else:
        verification_state = "verified"

    return {
        "queries": queries,
        "required_providers": required_providers,
        "missing_providers": missing_providers,
        "providers": providers,
        "provider_summary": provider_summary,
        "contradictions": contradictions,
        "notes": str(verification.get("notes") or "").strip(),
        "verification_state": verification_state,
    }


def _normalize_provider_results(raw_providers: Any) -> list[dict[str, Any]]:
    if raw_providers is None:
        return []
    if isinstance(raw_providers, dict):
        providers = [raw_providers]
    else:
        providers = list(raw_providers)
    normalized: list[dict[str, Any]] = []
    seen: set[str] = set()
    for raw_provider in providers:
        if not isinstance(raw_provider, dict):
            raise IdeaVerificationValidationError("Each provider result must be an object.")
        provider = str(raw_provider.get("provider") or "").strip()
        if not provider:
            raise IdeaVerificationValidationError("Provider result requires non-empty provider.")
        if provider in seen:
            raise IdeaVerificationValidationError(f"Duplicate provider result for {provider}.")
        seen.add(provider)

        status = str(raw_provider.get("status") or "").strip().lower()
        if status not in _PROVIDER_STATUSES:
            raise IdeaVerificationValidationError(
                f"Provider result for {provider} has invalid status: {status}"
            )

        evidence = _normalize_provider_evidence(raw_provider.get("evidence"))
        normalized.append(
            {
                "provider": provider,
                "status": status,
                "query": str(raw_provider.get("query") or "").strip(),
                "error": str(raw_provider.get("error") or "").strip(),
                "evidence": evidence,
            }
        )
    return normalized


def _normalize_provider_evidence(raw_items: Any) -> list[dict[str, str]]:
    if raw_items is None:
        return []
    if isinstance(raw_items, dict):
        items = [raw_items]
    else:
        items = list(raw_items)
    normalized: list[dict[str, str]] = []
    for raw_item in items[:_MAX_PROVIDER_EVIDENCE]:
        if not isinstance(raw_item, dict):
            raw_item = {"ref": str(raw_item)}
        excerpt = str(raw_item.get("excerpt") or "").strip()
        if len(excerpt) > _MAX_EXCERPT_CHARS:
            excerpt = excerpt[: _MAX_EXCERPT_CHARS - 3].rstrip() + "..."
        normalized.append(
            {
                "title": str(raw_item.get("title") or "").strip(),
                "url": str(raw_item.get("url") or "").strip(),
                "stance": str(raw_item.get("stance") or "").strip(),
                "excerpt": excerpt,
            }
        )
    return normalized


def _normalize_evidence_items(raw_items: Any) -> list[dict[str, str]]:
    if raw_items is None:
        return []
    if isinstance(raw_items, dict):
        items = [raw_items]
    else:
        items = list(raw_items)

    normalized: list[dict[str, str]] = []
    for raw_item in items:
        if isinstance(raw_item, dict):
            item = {
                "ref": str(raw_item.get("ref") or raw_item.get("path") or raw_item.get("page") or "").strip(),
                "title": str(raw_item.get("title") or "").strip(),
                "summary": str(raw_item.get("summary") or raw_item.get("note") or "").strip(),
                "view_key": str(raw_item.get("view_key") or "").strip(),
                "excerpt": str(raw_item.get("excerpt") or "").strip(),
            }
        else:
            item = {
                "ref": str(raw_item).strip(),
                "title": "",
                "summary": "",
                "view_key": "",
                "excerpt": "",
            }

        if len(item["excerpt"]) > _MAX_EXCERPT_CHARS:
            item["excerpt"] = item["excerpt"][: _MAX_EXCERPT_CHARS - 3].rstrip() + "..."

        if not any(item.values()):
            continue
        normalized.append(item)
    return normalized


def _normalize_string_list(raw_items: Any) -> list[str]:
    if raw_items is None:
        return []
    if isinstance(raw_items, str):
        candidates = [raw_items]
    else:
        candidates = list(raw_items)

    normalized: list[str] = []
    seen: set[str] = set()
    for raw_item in candidates:
        item = str(raw_item or "").strip()
        if not item or item in seen:
            continue
        seen.add(item)
        normalized.append(item)
    return normalized


def _candidate_idea_id(idea: Any) -> str | None:
    if not isinstance(idea, dict):
        return None
    candidate = str(idea.get("idea_id") or "").strip()
    return candidate or None


def _decode_json(raw: Any) -> dict[str, Any]:
    if not raw:
        return {}
    try:
        decoded = json.loads(raw)
    except (TypeError, json.JSONDecodeError):
        return {}
    return decoded if isinstance(decoded, dict) else {}
