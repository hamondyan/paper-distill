"""First-class dialogue capture flow for advisory memory.

Dialogue capture turns memory-worthy conversation turns into explicit proposal
artifacts under ``insights/dialogues/``. Accepted proposals enqueue one durable
memory event, typically starting at ``provisional`` for later confirmation;
rejected proposals stay as dialogue artifacts only.
"""
from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

import yaml

from server.database import _now_iso
from server.memory_contract import validate_typed_memory_event
from server.memory_promotion import classify_memory_impact, validate_memory_promotion_boundary
from server.memory_runtime import MemoryEventValidationError, _normalize_requested_view_keys
from server.vault_contract import paper_distill_root, root_path
from server.vault_ops import ensure_vault_structure, write_markdown

_CAPTURE_ID_RE = re.compile(r"^[a-z0-9][a-z0-9_-]*$")
_CAPTURE_ACTIONS = {"propose", "accept", "reject"}
_FINAL_CAPTURE_STATES = {"accepted", "rejected"}
_MAX_EXCERPT_CHARS = 280


class DialogueCaptureValidationError(ValueError):
    """Raised when a dialogue capture request is structurally invalid."""


def capture_dialogue(
    vault_path: str,
    *,
    action: str,
    proposal: dict[str, Any] | None = None,
    capture_id: str | None = None,
    decision_note: str | None = None,
) -> dict[str, Any]:
    """Persist a dialogue capture proposal or resolve it."""
    candidate_capture_id = _candidate_capture_id(capture_id, proposal)
    try:
        normalized = _normalize_capture_request(
            action=action,
            proposal=proposal,
            capture_id=capture_id,
            decision_note=decision_note,
        )
    except DialogueCaptureValidationError as exc:
        return _capture_failure(
            mutation_id=None,
            capture_id=candidate_capture_id,
            error=str(exc),
            capture_state="unknown",
            dialogue_path=None,
        )

    from server.runtime import get_mutation_record, submit_mutation

    result = submit_mutation(
        vault_path,
        mutation_type="dialogue_capture",
        target_key=_capture_target_key(normalized),
        payload=normalized,
    )
    normalized_result = _normalize_capture_result(
        result,
        capture_id=normalized.get("capture_id"),
    )

    memory_mutation_id = normalized_result.get("memory_mutation_id")
    if not memory_mutation_id:
        return normalized_result

    memory_record = get_mutation_record(vault_path, int(memory_mutation_id))
    memory_result = dict(memory_record.get("result") or {})
    if memory_result.get("appended"):
        normalized_result["memory_write_state"] = "appended"
        normalized_result["memory_event_id"] = memory_result.get("event_id")
        normalized_result["memory_event_path"] = memory_result.get("event_path")
    elif memory_record.get("status") == "failed":
        normalized_result["memory_write_state"] = "failed"
        normalized_result["memory_error"] = (
            memory_result.get("error") or memory_record.get("error")
        )
    else:
        normalized_result["memory_write_state"] = "queued"
    return normalized_result


def execute_dialogue_capture_mutation(vault_path: str, mutation: dict[str, Any]) -> dict[str, Any]:
    """Single-writer handler for dialogue capture proposal and resolution."""
    ensure_vault_structure(vault_path)
    payload = _decode_json(mutation.get("payload_json"))
    candidate_capture_id = _candidate_capture_id(payload.get("capture_id"), payload.get("proposal"))

    try:
        request = _normalize_capture_request(
            action=payload.get("action"),
            proposal=payload.get("proposal"),
            capture_id=payload.get("capture_id"),
            decision_note=payload.get("decision_note"),
        )
    except DialogueCaptureValidationError as exc:
        return _capture_failure(
            mutation_id=mutation.get("id"),
            capture_id=candidate_capture_id,
            error=str(exc),
            capture_state="unknown",
            dialogue_path=None,
        )

    if request["action"] == "propose":
        return _execute_propose(vault_path, mutation, request)
    return _execute_resolution(vault_path, mutation, request)


def _execute_propose(
    vault_path: str,
    mutation: dict[str, Any],
    request: dict[str, Any],
) -> dict[str, Any]:
    proposal = dict(request["proposal"])
    capture_id = request.get("capture_id") or _capture_id_for_mutation(mutation)
    note_path = _dialogue_note_path(vault_path, capture_id)
    if note_path.exists():
        existing_frontmatter, _ = _read_markdown_note(note_path)
        return _capture_success(
            mutation_id=mutation["id"],
            capture_id=capture_id,
            dialogue_path=str(note_path),
            capture_state=str(existing_frontmatter.get("capture_state") or "proposed"),
            decision=str(existing_frontmatter.get("decision") or "pending"),
            memory_write_state=str(
                existing_frontmatter.get("memory_write_state") or "pending_user_decision"
            ),
            memory_mutation_id=_coerce_optional_int(existing_frontmatter.get("memory_mutation_id")),
            memory_error=_coerce_optional_str(existing_frontmatter.get("memory_error")),
        )

    created_at = str(mutation.get("created_at") or _now_iso())
    frontmatter = _build_dialogue_frontmatter(
        capture_id=capture_id,
        proposal=proposal,
        capture_state="proposed",
        decision="pending",
        created_at=created_at,
        updated_at=created_at,
        decision_note="",
        memory_write_state="pending_user_decision",
        memory_mutation_id=None,
        memory_error=None,
    )
    body = _build_dialogue_body(frontmatter)
    write_markdown(note_path, frontmatter, body)
    return _capture_success(
        mutation_id=mutation["id"],
        capture_id=capture_id,
        dialogue_path=str(note_path),
        capture_state="proposed",
        decision="pending",
        memory_write_state="pending_user_decision",
        memory_mutation_id=None,
        memory_error=None,
    )


def _execute_resolution(
    vault_path: str,
    mutation: dict[str, Any],
    request: dict[str, Any],
) -> dict[str, Any]:
    capture_id = str(request["capture_id"])
    action = str(request["action"])
    note_path = _dialogue_note_path(vault_path, capture_id)
    if not note_path.exists():
        return _capture_failure(
            mutation_id=mutation["id"],
            capture_id=capture_id,
            error=f"Dialogue capture {capture_id} does not exist.",
            capture_state="unknown",
            dialogue_path=str(note_path),
        )

    frontmatter, _ = _read_markdown_note(note_path)
    current_state = str(frontmatter.get("capture_state") or "unknown")
    if current_state in _FINAL_CAPTURE_STATES:
        if (current_state == "accepted" and action == "accept") or (
            current_state == "rejected" and action == "reject"
        ):
            return _capture_success(
                mutation_id=mutation["id"],
                capture_id=capture_id,
                dialogue_path=str(note_path),
                capture_state=current_state,
                decision=str(frontmatter.get("decision") or action),
                memory_write_state=str(frontmatter.get("memory_write_state") or "skipped"),
                memory_mutation_id=_coerce_optional_int(frontmatter.get("memory_mutation_id")),
                memory_error=_coerce_optional_str(frontmatter.get("memory_error")),
            )
        return _capture_failure(
            mutation_id=mutation["id"],
            capture_id=capture_id,
            error=(
                f"Dialogue capture {capture_id} is already {current_state} and cannot be "
                f"resolved as {action}."
            ),
            capture_state=current_state,
            dialogue_path=str(note_path),
        )

    updated_at = str(mutation.get("created_at") or _now_iso())
    decision_note = str(request.get("decision_note") or "").strip()
    if action == "reject":
        updated = dict(frontmatter)
        updated.update(
            {
                "capture_state": "rejected",
                "decision": "reject",
                "decision_note": decision_note,
                "updated": updated_at,
                "memory_write_state": "skipped",
                "memory_mutation_id": None,
                "memory_error": None,
            }
        )
        write_markdown(note_path, updated, _build_dialogue_body(updated))
        return _capture_success(
            mutation_id=mutation["id"],
            capture_id=capture_id,
            dialogue_path=str(note_path),
            capture_state="rejected",
            decision="reject",
            memory_write_state="skipped",
            memory_mutation_id=None,
            memory_error=None,
        )

    event = _memory_event_from_dialogue_frontmatter(vault_path, note_path, frontmatter)
    memory_enqueue = _enqueue_memory_append(vault_path, event)
    updated = dict(frontmatter)
    updated.update(
        {
            "capture_state": "accepted",
            "decision": "accept",
            "decision_note": decision_note,
            "updated": updated_at,
            "memory_write_state": str(memory_enqueue.get("state") or "queued"),
            "memory_mutation_id": memory_enqueue.get("mutation_id"),
            "memory_error": memory_enqueue.get("error"),
        }
    )
    write_markdown(note_path, updated, _build_dialogue_body(updated))

    if memory_enqueue.get("error"):
        return _capture_failure(
            mutation_id=mutation["id"],
            capture_id=capture_id,
            error=str(memory_enqueue["error"]),
            capture_state="accepted",
            dialogue_path=str(note_path),
            memory_write_state="failed",
            memory_mutation_id=memory_enqueue.get("mutation_id"),
            memory_error=str(memory_enqueue["error"]),
        )

    return _capture_success(
        mutation_id=mutation["id"],
        capture_id=capture_id,
        dialogue_path=str(note_path),
        capture_state="accepted",
        decision="accept",
        memory_write_state=str(memory_enqueue.get("state") or "queued"),
        memory_mutation_id=memory_enqueue.get("mutation_id"),
        memory_error=None,
    )


def _normalize_capture_request(
    *,
    action: Any,
    proposal: Any,
    capture_id: Any,
    decision_note: Any,
) -> dict[str, Any]:
    normalized_action = str(action or "").strip().lower()
    if normalized_action not in _CAPTURE_ACTIONS:
        raise DialogueCaptureValidationError(
            "Dialogue capture action must be propose, accept, or reject."
        )

    normalized_capture_id = _normalize_capture_id(capture_id)
    normalized_decision_note = str(decision_note or "").strip()
    normalized_proposal = None
    if normalized_action == "propose":
        normalized_proposal = _normalize_dialogue_proposal(proposal)
        if not normalized_capture_id:
            normalized_capture_id = _normalize_capture_id(
                normalized_proposal.get("capture_id")
            )
    else:
        if not normalized_capture_id:
            raise DialogueCaptureValidationError(
                "Dialogue capture accept/reject requires capture_id."
            )

    return {
        "action": normalized_action,
        "capture_id": normalized_capture_id,
        "proposal": normalized_proposal,
        "decision_note": normalized_decision_note,
    }


def _normalize_dialogue_proposal(proposal: Any) -> dict[str, Any]:
    if not isinstance(proposal, dict):
        raise DialogueCaptureValidationError("Dialogue capture proposal must be an object.")

    summary = str(proposal.get("summary") or "").strip()
    if not summary:
        raise DialogueCaptureValidationError(
            "Dialogue capture proposal requires non-empty summary."
        )

    trust_label = str(proposal.get("trust_label") or "").strip()
    if not trust_label:
        raise DialogueCaptureValidationError(
            "Dialogue capture proposal requires non-empty trust_label."
        )

    title = str(proposal.get("title") or "").strip() or summary[:120]
    view_keys = _normalize_requested_view_keys(
        proposal.get("view_keys")
        if proposal.get("view_keys") is not None
        else ([proposal.get("view_key")] if proposal.get("view_key") is not None else None)
    )
    if not view_keys:
        raise DialogueCaptureValidationError(
            "Dialogue capture proposal requires at least one view_key."
        )

    accepted_status = str(proposal.get("accepted_status") or "provisional").strip() or "provisional"
    source = dict(proposal.get("source") or {})
    source_kind = str(source.get("kind") or "dialogue").strip() or "dialogue"
    source_turn_id = str(source.get("turn_id") or "").strip()
    source_conversation_id = str(source.get("conversation_id") or "").strip()
    source_ref = str(source.get("ref") or "").strip()
    if not (source_turn_id or source_conversation_id or source_ref):
        raise DialogueCaptureValidationError(
            "Dialogue capture proposal requires source.turn_id, source.conversation_id, or source.ref."
        )

    evidence_excerpt = str(
        proposal.get("evidence_excerpt")
        or proposal.get("quote")
        or ""
    ).strip()
    if len(evidence_excerpt) > _MAX_EXCERPT_CHARS:
        evidence_excerpt = evidence_excerpt[: _MAX_EXCERPT_CHARS - 3].rstrip() + "..."

    validation_event = {
        "event_type": "dialogue_capture",
        "title": title,
        "summary": summary,
        "content": str(proposal.get("content") or "").strip(),
        "view_keys": view_keys,
        "trust_label": trust_label,
        "status": accepted_status,
        "source": {
            "kind": source_kind,
            "turn_id": source_turn_id,
            "conversation_id": source_conversation_id,
            "ref": source_ref,
        },
        "metadata": dict(proposal.get("metadata") or {}),
    }

    normalized = {
        "capture_id": _normalize_capture_id(proposal.get("capture_id")),
        "title": title,
        "summary": summary,
        "content": validation_event["content"],
        "proposal_note": str(proposal.get("proposal_note") or proposal.get("rationale") or "").strip(),
        "evidence_excerpt": evidence_excerpt,
        "view_keys": view_keys,
        "trust_label": trust_label,
        "accepted_status": accepted_status,
        "source": dict(validation_event["source"]),
        "metadata": dict(validation_event["metadata"]),
        "impact_level": classify_memory_impact(validation_event),
    }
    normalized["promotion_required"] = normalized["impact_level"] == "high"

    try:
        validate_typed_memory_event(validation_event)
        validate_memory_promotion_boundary(validation_event)
    except (ValueError, MemoryEventValidationError) as exc:
        raise DialogueCaptureValidationError(str(exc)) from exc
    return normalized


def _memory_event_from_dialogue_frontmatter(
    vault_path: str,
    note_path: Path,
    frontmatter: dict[str, Any],
) -> dict[str, Any]:
    dialogue_ref = _paper_distill_ref(vault_path, note_path)
    source = dict(frontmatter.get("source") or {})
    source.update(
        {
            "kind": str(source.get("kind") or "dialogue"),
            "dialogue_capture_id": frontmatter["capture_id"],
            "dialogue_ref": dialogue_ref,
        }
    )
    metadata = dict(frontmatter.get("metadata") or {})
    metadata.update(
        {
            "dialogue_capture_id": frontmatter["capture_id"],
            "dialogue_ref": dialogue_ref,
        }
    )
    return {
        "event_type": "dialogue_capture",
        "title": str(frontmatter.get("title") or frontmatter.get("summary") or "")[:120],
        "summary": str(frontmatter.get("summary") or "").strip(),
        "content": str(frontmatter.get("content") or "").strip(),
        "view_keys": list(frontmatter.get("view_keys") or []),
        "trust_label": str(frontmatter.get("trust_label") or "").strip(),
        "status": str(frontmatter.get("accepted_status") or "provisional").strip() or "provisional",
        "source": source,
        "metadata": metadata,
    }


def _enqueue_memory_append(vault_path: str, event: dict[str, Any]) -> dict[str, Any]:
    try:
        from server.runtime import enqueue_mutation

        enqueued = enqueue_mutation(
            vault_path,
            mutation_type="memory_append",
            target_key="memory:events",
            payload={"event": event},
        )
    except Exception as exc:
        return {"state": "failed", "error": f"Failed to enqueue dialogue memory append: {exc}"}
    return {"state": "queued", "mutation_id": enqueued.get("mutation_id")}


def _build_dialogue_frontmatter(
    *,
    capture_id: str,
    proposal: dict[str, Any],
    capture_state: str,
    decision: str,
    created_at: str,
    updated_at: str,
    decision_note: str,
    memory_write_state: str,
    memory_mutation_id: int | None,
    memory_error: str | None,
) -> dict[str, Any]:
    return {
        "type": "dialogue-capture",
        "section": "insights/dialogues",
        "capture_id": capture_id,
        "capture_state": capture_state,
        "decision": decision,
        "title": proposal["title"],
        "summary": proposal["summary"],
        "view_keys": list(proposal["view_keys"]),
        "trust_label": proposal["trust_label"],
        "accepted_status": proposal["accepted_status"],
        "source": dict(proposal["source"]),
        "proposal_note": proposal["proposal_note"],
        "evidence_excerpt": proposal["evidence_excerpt"],
        "content": proposal["content"],
        "metadata": dict(proposal["metadata"]),
        "impact_level": proposal.get("impact_level") or "low",
        "promotion_required": bool(proposal.get("promotion_required")),
        "created": created_at,
        "updated": updated_at,
        "decision_note": decision_note,
        "memory_write_state": memory_write_state,
        "memory_mutation_id": memory_mutation_id,
        "memory_error": memory_error,
    }


def _build_dialogue_body(frontmatter: dict[str, Any]) -> str:
    source = dict(frontmatter.get("source") or {})
    lines = [
        f"# {frontmatter.get('title') or 'Dialogue Capture'}",
        "",
        "## Summary",
        "",
        str(frontmatter.get("summary") or "").strip() or "No summary captured.",
        "",
        "## Proposed Memory",
        "",
        f"- View keys: {', '.join(frontmatter.get('view_keys') or []) or 'none'}",
        f"- Trust label: {frontmatter.get('trust_label') or 'unknown'}",
        f"- Accepted status: {frontmatter.get('accepted_status') or 'provisional'}",
        f"- Impact level: {frontmatter.get('impact_level') or 'low'}",
        f"- Explicit promotion required: {'yes' if frontmatter.get('promotion_required') else 'no'}",
        f"- Source kind: {source.get('kind') or 'dialogue'}",
        f"- Source turn: {source.get('turn_id') or 'none'}",
        f"- Source conversation: {source.get('conversation_id') or 'none'}",
        f"- Source ref: {source.get('ref') or 'none'}",
    ]

    proposal_note = str(frontmatter.get("proposal_note") or "").strip()
    if proposal_note:
        lines.extend(["", "## Why This Matters", "", proposal_note])

    evidence_excerpt = str(frontmatter.get("evidence_excerpt") or "").strip()
    if evidence_excerpt:
        lines.extend(["", "## Evidence Excerpt", "", f"> {evidence_excerpt}"])

    content = str(frontmatter.get("content") or "").strip()
    if content:
        lines.extend(["", "## Memory Content", "", content])

    lines.extend(
        [
            "",
            "## Decision",
            "",
            f"- Capture state: {frontmatter.get('capture_state') or 'unknown'}",
            f"- Decision: {frontmatter.get('decision') or 'pending'}",
            f"- Decision note: {frontmatter.get('decision_note') or 'none'}",
            f"- Memory write state: {frontmatter.get('memory_write_state') or 'none'}",
            f"- Memory mutation id: {frontmatter.get('memory_mutation_id') or 'none'}",
        ]
    )
    memory_error = str(frontmatter.get("memory_error") or "").strip()
    if memory_error:
        lines.append(f"- Memory error: {memory_error}")
    return "\n".join(lines).strip()


def _capture_success(
    *,
    mutation_id: int | None,
    capture_id: str,
    dialogue_path: str,
    capture_state: str,
    decision: str,
    memory_write_state: str,
    memory_mutation_id: int | None,
    memory_error: str | None,
) -> dict[str, Any]:
    return {
        "ok": True,
        "mutation_id": mutation_id,
        "capture_id": capture_id,
        "dialogue_path": dialogue_path,
        "capture_state": capture_state,
        "decision": decision,
        "memory_write_state": memory_write_state,
        "memory_mutation_id": memory_mutation_id,
        "memory_error": memory_error,
    }


def _capture_failure(
    *,
    mutation_id: int | None,
    capture_id: str | None,
    error: str,
    capture_state: str,
    dialogue_path: str | None,
    memory_write_state: str = "skipped",
    memory_mutation_id: int | None = None,
    memory_error: str | None = None,
) -> dict[str, Any]:
    return {
        "ok": False,
        "mutation_id": mutation_id,
        "capture_id": capture_id,
        "dialogue_path": dialogue_path,
        "capture_state": capture_state,
        "decision": "pending" if capture_state == "unknown" else capture_state,
        "memory_write_state": memory_write_state,
        "memory_mutation_id": memory_mutation_id,
        "memory_error": memory_error,
        "error": error,
    }


def _normalize_capture_result(result: dict[str, Any], *, capture_id: str | None) -> dict[str, Any]:
    normalized = dict(result)
    normalized.setdefault("capture_id", capture_id)
    normalized.setdefault("memory_write_state", "skipped")
    normalized.setdefault("memory_mutation_id", None)
    normalized.setdefault("memory_error", None)
    if "capture_state" in normalized and "dialogue_path" in normalized:
        return normalized
    return _capture_failure(
        mutation_id=normalized.get("mutation_id"),
        capture_id=capture_id,
        error=str(normalized.get("error") or "dialogue capture failed"),
        capture_state=str(normalized.get("capture_state") or "unknown"),
        dialogue_path=normalized.get("dialogue_path"),
        memory_write_state=str(normalized.get("memory_write_state") or "skipped"),
        memory_mutation_id=_coerce_optional_int(normalized.get("memory_mutation_id")),
        memory_error=_coerce_optional_str(normalized.get("memory_error")),
    )


def _read_markdown_note(path: Path) -> tuple[dict[str, Any], str]:
    content = path.read_text(encoding="utf-8")
    if not content.startswith("---\n"):
        return {}, content.strip()
    _, remainder = content.split("---\n", 1)
    fm_text, body = remainder.split("\n---\n", 1)
    frontmatter = yaml.safe_load(fm_text) or {}
    if not isinstance(frontmatter, dict):
        frontmatter = {}
    return frontmatter, body.strip()


def _dialogue_note_path(vault_path: str, capture_id: str) -> Path:
    return root_path(vault_path, "dialogues") / f"{capture_id}.md"


def _capture_target_key(request: dict[str, Any]) -> str:
    capture_id = request.get("capture_id")
    if capture_id:
        return f"dialogue:{capture_id}"
    proposal = dict(request.get("proposal") or {})
    source = dict(proposal.get("source") or {})
    source_key = (
        source.get("turn_id")
        or source.get("conversation_id")
        or source.get("ref")
        or proposal.get("summary")
        or "new"
    )
    return f"dialogue:proposal:{str(source_key).strip()}"


def _capture_id_for_mutation(mutation: dict[str, Any]) -> str:
    return f"dialogue-capture-{int(mutation['id']):08d}"


def _normalize_capture_id(raw_capture_id: Any) -> str | None:
    candidate = str(raw_capture_id or "").strip()
    if not candidate:
        return None
    if not _CAPTURE_ID_RE.match(candidate):
        raise DialogueCaptureValidationError(f"Invalid capture_id: {candidate}")
    return candidate


def _candidate_capture_id(capture_id: Any, proposal: Any) -> str | None:
    try:
        normalized = _normalize_capture_id(capture_id)
    except DialogueCaptureValidationError:
        return None
    if normalized:
        return normalized
    if not isinstance(proposal, dict):
        return None
    try:
        return _normalize_capture_id(proposal.get("capture_id"))
    except DialogueCaptureValidationError:
        return None


def _paper_distill_ref(vault_path: str, path: Path) -> str:
    root = paper_distill_root(vault_path)
    return f"Paper Distill/{path.relative_to(root).as_posix()}"


def _coerce_optional_int(value: Any) -> int | None:
    try:
        if value is None or value == "":
            return None
        return int(value)
    except (TypeError, ValueError):
        return None


def _coerce_optional_str(value: Any) -> str | None:
    text = str(value or "").strip()
    return text or None


def _decode_json(raw: Any) -> dict[str, Any]:
    if not raw:
        return {}
    try:
        decoded = json.loads(raw)
    except (TypeError, json.JSONDecodeError):
        return {}
    return decoded if isinstance(decoded, dict) else {}
