"""Promotion and confirmation helpers for advisory memory.

This lane makes the provisional -> confirmed boundary explicit for high-impact
memory. The source event history remains append-only:

- initial capture writes a provisional event
- explicit promotion writes an audit artifact and appends a promoted event
- current views collapse superseded provisional source events
"""
from __future__ import annotations

import uuid
from pathlib import Path
from typing import Any

from server.database import _now_iso
from server.vault_contract import root_path
from server.vault_ops import ensure_vault_structure, write_markdown

HIGH_IMPACT_VIEW_KEYS = frozenset({"assistant-brief", "profile", "taste"})
HIGH_IMPACT_METADATA_KEYS = frozenset(
    {
        "accepted_keywords",
        "rejected_keywords",
        "preferred_venues",
        "whitelist_authors",
        "seed_papers",
        "direction",
        "profile_direction",
        "research_direction",
    }
)
PROMOTION_TARGET_STATUSES = frozenset({"confirmed", "consolidated"})
RUNTIME_CONFIRMED_STATUSES = frozenset({"confirmed", "consolidated"})


def classify_memory_impact(event: dict[str, Any]) -> str:
    """Classify memory impact deterministically from view keys and metadata."""
    view_keys = {str(item or "").strip() for item in event.get("view_keys") or []}
    metadata = dict(event.get("metadata") or {})

    if view_keys.intersection(HIGH_IMPACT_VIEW_KEYS):
        return "high"
    if any(key in metadata and metadata.get(key) not in (None, "", [], {}) for key in HIGH_IMPACT_METADATA_KEYS):
        return "high"
    return "low"


def validate_memory_promotion_boundary(event: dict[str, Any]) -> None:
    """Reject direct high-impact writes that skip the provisional stage."""
    status = str(event.get("status") or "").strip()
    if status not in PROMOTION_TARGET_STATUSES:
        return
    if classify_memory_impact(event) != "high":
        return

    metadata = dict(event.get("metadata") or {})
    if _is_promotion_event_metadata(metadata):
        return

    raise ValueError(
        "High-impact memory cannot be written directly as confirmed or consolidated. "
        "Write it as provisional first, then promote it explicitly."
    )


def collapse_promoted_memory_events(events: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Hide superseded source events once a promoted clone exists."""
    superseded_event_ids = {
        str(dict(event.get("metadata") or {}).get("promotion_source_event_id") or "").strip()
        for event in events
        if str(event.get("status") or "").strip() in PROMOTION_TARGET_STATUSES
        and _is_promotion_event_metadata(dict(event.get("metadata") or {}))
    }
    superseded_event_ids.discard("")
    if not superseded_event_ids:
        return list(events)

    return [
        event
        for event in events
        if str(event.get("event_id") or "").strip() not in superseded_event_ids
    ]


def runtime_effective_memory_events(view_key: str, events: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Return the events that should actively shape runtime behavior."""
    collapsed = collapse_promoted_memory_events(events)
    if view_key not in HIGH_IMPACT_VIEW_KEYS:
        return collapsed
    return [
        event
        for event in collapsed
        if str(event.get("status") or "").strip() in RUNTIME_CONFIRMED_STATUSES
    ]


def promote_memory_event(
    vault_path: str,
    *,
    source_event_id: str,
    promoted_status: str = "confirmed",
    decision_note: str | None = None,
) -> dict[str, Any]:
    """Promote one existing provisional memory event directly."""
    try:
        normalized = _normalize_promotion_request(
            source_event_id=source_event_id,
            promoted_status=promoted_status,
            decision_note=decision_note,
        )
    except ValueError as exc:
        return {
            "ok": False,
            "promoted": False,
            "error": str(exc),
        }

    return _commit_memory_promotion(vault_path, normalized, created_at=_now_iso())


def _commit_memory_promotion(
    vault_path: str,
    request: dict[str, Any],
    *,
    created_at: str,
) -> dict[str, Any]:
    ensure_vault_structure(vault_path)
    source_event = _find_memory_event(vault_path, request["source_event_id"])
    if source_event is None:
        return {
            "ok": False,
            "promoted": False,
            "error": f"Memory event {request['source_event_id']} does not exist.",
        }

    existing_promotion = _find_existing_promotion(vault_path, request["source_event_id"])
    if existing_promotion is not None:
        artifact_path = _promotion_note_path(vault_path, request["source_event_id"], request["promoted_status"])
        return {
            "ok": True,
            "promoted": True,
            "already_promoted": True,
            "impact_level": classify_memory_impact(source_event),
            "source_event_id": request["source_event_id"],
            "promoted_status": str(existing_promotion.get("status") or request["promoted_status"]),
            "promotion_artifact_path": str(artifact_path),
            "promoted_event_id": existing_promotion.get("event_id"),
        }

    source_status = str(source_event.get("status") or "").strip()
    if source_status != "provisional":
        return {
            "ok": False,
            "promoted": False,
            "error": (
                f"Memory event {request['source_event_id']} must be provisional before promotion; "
                f"found {source_status or 'unknown'}."
            ),
        }

    impact_level = classify_memory_impact(source_event)
    artifact_path = _promotion_note_path(
        vault_path,
        request["source_event_id"],
        request["promoted_status"],
    )
    artifact_frontmatter = _build_promotion_frontmatter(
        source_event=source_event,
        request=request,
        impact_level=impact_level,
        created_at=created_at,
        promotion_id=_promotion_id_for_now(created_at),
    )
    artifact_body = _build_promotion_body(
        source_event=source_event,
        request=request,
        impact_level=impact_level,
    )
    write_markdown(artifact_path, artifact_frontmatter, artifact_body)

    promotion_ref = _paper_distill_ref(vault_path, artifact_path)
    promoted_event = _build_promoted_event(
        source_event=source_event,
        request=request,
        impact_level=impact_level,
        promotion_ref=promotion_ref,
        promotion_id=artifact_frontmatter["promotion_id"],
    )

    from server.memory_runtime import append_memory_event

    append_result = append_memory_event(
        vault_path,
        event=promoted_event,
        created_at=created_at,
    )
    if not append_result.get("ok"):
        return {
            "ok": False,
            "promoted": False,
            "promotion_artifact_path": str(artifact_path),
            "error": str(append_result.get("error") or "Failed to append promoted memory."),
            "promoted_event_state": "failed",
            "promoted_event_id": None,
            "promoted_event_path": None,
            "promoted_event_error": str(append_result.get("error") or ""),
        }

    return {
        "ok": True,
        "promoted": True,
        "already_promoted": False,
        "impact_level": impact_level,
        "source_event_id": request["source_event_id"],
        "promoted_status": request["promoted_status"],
        "promotion_artifact_path": str(artifact_path),
        "promoted_event_state": "appended",
        "promoted_event_id": append_result.get("event_id"),
        "promoted_event_path": append_result.get("event_path"),
        "promoted_event_error": None,
    }


def _normalize_promotion_request(
    *,
    source_event_id: Any,
    promoted_status: Any,
    decision_note: Any,
) -> dict[str, Any]:
    normalized_source_event_id = str(source_event_id or "").strip()
    if not normalized_source_event_id:
        raise ValueError("Memory promotion requires source_event_id.")

    normalized_status = str(promoted_status or "confirmed").strip() or "confirmed"
    if normalized_status not in PROMOTION_TARGET_STATUSES:
        raise ValueError(
            "Memory promotion target status must be confirmed or consolidated."
        )

    return {
        "source_event_id": normalized_source_event_id,
        "promoted_status": normalized_status,
        "decision_note": str(decision_note or "").strip(),
    }


def _normalize_promotion_result(result: dict[str, Any], *, source_event_id: str) -> dict[str, Any]:
    normalized = dict(result)
    normalized.setdefault("source_event_id", source_event_id)
    if "promoted" in normalized:
        normalized.setdefault("promoted_event_state", "skipped")
        normalized.setdefault("promoted_event_id", None)
        normalized.setdefault("promoted_event_path", None)
        normalized.setdefault("promoted_event_error", None)
        return normalized

    return {
        "ok": False,
        "promoted": False,
        "source_event_id": source_event_id,
        "promotion_artifact_path": normalized.get("promotion_artifact_path"),
        "promoted_event_state": "skipped",
        "promoted_event_id": None,
        "promoted_event_path": None,
        "promoted_event_error": None,
        "error": str(normalized.get("error") or "memory promotion failed"),
    }


def _find_memory_event(vault_path: str, event_id: str) -> dict[str, Any] | None:
    from server.memory_runtime import list_memory_events

    for event in list_memory_events(vault_path):
        if str(event.get("event_id") or "").strip() == event_id:
            return event
    return None


def _find_existing_promotion(vault_path: str, source_event_id: str) -> dict[str, Any] | None:
    from server.memory_runtime import list_memory_events

    for event in list_memory_events(vault_path):
        metadata = dict(event.get("metadata") or {})
        if str(metadata.get("promotion_source_event_id") or "").strip() != source_event_id:
            continue
        if str(event.get("status") or "").strip() not in PROMOTION_TARGET_STATUSES:
            continue
        return event
    return None


def _build_promoted_event(
    *,
    source_event: dict[str, Any],
    request: dict[str, Any],
    impact_level: str,
    promotion_ref: str,
    promotion_id: str,
) -> dict[str, Any]:
    metadata = dict(source_event.get("metadata") or {})
    metadata.update(
        {
            "promotion_source_event_id": source_event.get("event_id"),
            "promotion_source_status": source_event.get("status"),
            "promotion_id": promotion_id,
            "promotion_artifact_ref": promotion_ref,
            "promotion_decision_note": request["decision_note"],
            "impact_level": impact_level,
        }
    )
    return {
        "event_type": source_event.get("event_type"),
        "title": source_event.get("title"),
        "summary": source_event.get("summary"),
        "content": source_event.get("content"),
        "view_keys": list(source_event.get("view_keys") or []),
        "trust_label": source_event.get("trust_label"),
        "status": request["promoted_status"],
        "source": dict(source_event.get("source") or {}),
        "metadata": metadata,
    }


def _build_promotion_frontmatter(
    *,
    source_event: dict[str, Any],
    request: dict[str, Any],
    impact_level: str,
    created_at: str,
    promotion_id: str,
) -> dict[str, Any]:
    title = str(source_event.get("title") or source_event.get("summary") or "Memory Promotion").strip()
    return {
        "type": "memory-promotion",
        "section": "insights/memory-promotions",
        "promotion_id": promotion_id,
        "title": f"Confirm memory: {title[:100]}",
        "source_event_id": source_event.get("event_id"),
        "source_status": source_event.get("status"),
        "target_status": request["promoted_status"],
        "view_keys": list(source_event.get("view_keys") or []),
        "impact_level": impact_level,
        "created": created_at,
        "updated": created_at,
        "decision_note": request["decision_note"],
        "source_event_path": str(source_event.get("event_path") or ""),
    }


def _build_promotion_body(
    *,
    source_event: dict[str, Any],
    request: dict[str, Any],
    impact_level: str,
) -> str:
    lines = [
        f"# Confirm Memory: {source_event.get('title') or source_event.get('summary') or 'Untitled'}",
        "",
        "## Promotion",
        "",
        f"- Source event: {source_event.get('event_id') or 'unknown'}",
        f"- From status: {source_event.get('status') or 'unknown'}",
        f"- To status: {request['promoted_status']}",
        f"- Impact level: {impact_level}",
        f"- View keys: {', '.join(source_event.get('view_keys') or []) or 'none'}",
        "",
        "## Summary",
        "",
        str(source_event.get("summary") or "").strip() or "No summary recorded.",
    ]

    content = str(source_event.get("content") or "").strip()
    if content:
        lines.extend(["", "## Memory Content", "", content])

    decision_note = str(request.get("decision_note") or "").strip()
    if decision_note:
        lines.extend(["", "## Decision Note", "", decision_note])

    return "\n".join(lines).strip() + "\n"


def _promotion_note_path(vault_path: str, source_event_id: str, promoted_status: str) -> Path:
    return (
        root_path(vault_path, "memory_promotions")
        / f"{source_event_id}-{promoted_status}.md"
    )


def _promotion_id_for_now(created_at: str) -> str:
    stamp = "".join(ch for ch in created_at if ch.isdigit())[:14] or "promotion"
    return f"memory-promotion-{stamp}-{uuid.uuid4().hex[:8]}"


def _paper_distill_ref(vault_path: str, path: Path) -> str:
    root = Path(vault_path).expanduser() / "Paper Distill"
    try:
        relative = path.expanduser().resolve().relative_to(root.resolve())
    except Exception:
        return str(path)
    return f"Paper Distill/{relative.as_posix()}"


def _is_promotion_event_metadata(metadata: dict[str, Any]) -> bool:
    return bool(
        str(metadata.get("promotion_source_event_id") or "").strip()
        and str(metadata.get("promotion_artifact_ref") or "").strip()
    )
