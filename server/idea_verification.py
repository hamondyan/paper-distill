"""Wave 1 idea verification runtime with durable memo gating.

Idea verification persists structured snapshots under ``insights/verification``
and writes idea memos under ``insights/ideas``. Snapshot persistence is the hard
gate. Durable memo promotion only happens after a snapshot is written
successfully. Provider failure, partial evidence, and contradiction all keep
the idea in draft state.
"""
from __future__ import annotations

import json
import os
import re
import uuid
from pathlib import Path
from typing import Any

from server.database import _now_iso
from server.vault_contract import (
    assert_supported_write_path,
    paper_distill_root,
    root_path,
)
from server.vault_ops import ensure_vault_structure, write_markdown

_SCHEMA_VERSION = "2026-04-09"
_IDEA_ID_RE = re.compile(r"^[a-z0-9][a-z0-9_-]*$")
_LAYER_ORDER = ("wiki", "sources", "memory")
_PROVIDER_STATUSES = {"succeeded", "failed", "partial", "contradicted"}
_MAX_PROVIDER_EVIDENCE = 5
_MAX_EXCERPT_CHARS = 400


class IdeaVerificationValidationError(ValueError):
    """Raised when an idea verification request is structurally invalid."""


class VerificationSnapshotPersistError(RuntimeError):
    """Raised when a verification snapshot cannot be read or written durably."""


class VerificationProviderError(RuntimeError):
    """Named provider failure for callers that live-hit external verification."""


def verify_idea(
    vault_path: str,
    *,
    idea: dict[str, Any],
    verification: dict[str, Any],
) -> dict[str, Any]:
    """Persist a verification snapshot and gate durable memo promotion."""
    candidate_idea_id = _candidate_idea_id(idea)
    try:
        normalized_idea = _normalize_idea_request(idea)
        normalized_verification = _normalize_verification_request(verification)
    except IdeaVerificationValidationError as exc:
        return _failure_result(
            mutation_id=None,
            idea_id=candidate_idea_id,
            error=str(exc),
            verification_state="unknown",
            snapshot_persisted=False,
        )

    from server.runtime import submit_mutation

    result = submit_mutation(
        vault_path,
        mutation_type="idea_verify",
        target_key=f"idea:{normalized_idea['idea_id']}",
        payload={
            "idea": normalized_idea,
            "verification": normalized_verification,
        },
    )
    return _normalize_verify_result(result, idea_id=normalized_idea["idea_id"])


def execute_idea_verify_mutation(vault_path: str, mutation: dict[str, Any]) -> dict[str, Any]:
    """Single-writer handler for verification snapshot persistence and memo gating."""
    ensure_vault_structure(vault_path)
    payload = _decode_json(mutation.get("payload_json"))
    candidate_idea_id = _candidate_idea_id(payload.get("idea"))

    try:
        idea = _normalize_idea_request(payload.get("idea") or {})
        verification = _normalize_verification_request(payload.get("verification") or {})
    except IdeaVerificationValidationError as exc:
        return _failure_result(
            mutation_id=mutation.get("id"),
            idea_id=candidate_idea_id,
            error=str(exc),
            verification_state="unknown",
            snapshot_persisted=False,
        )

    snapshot = _materialize_snapshot(mutation, idea, verification)
    snapshot_path = _snapshot_path_for_mutation(vault_path, mutation, idea["idea_id"])
    try:
        if snapshot_path.exists():
            persisted_snapshot = _read_snapshot_file(snapshot_path)
        else:
            _atomic_write_json(snapshot_path, snapshot)
            persisted_snapshot = snapshot
    except (OSError, VerificationSnapshotPersistError) as exc:
        return _failure_result(
            mutation_id=mutation["id"],
            idea_id=idea["idea_id"],
            error=f"Failed to persist verification snapshot {snapshot['snapshot_id']}: {exc}",
            verification_state=snapshot["verification_state"],
            snapshot_persisted=False,
            snapshot_path=str(snapshot_path),
            snapshot_id=snapshot["snapshot_id"],
        )

    promoted = bool(persisted_snapshot.get("promotion_eligible"))
    memo_path = _idea_memo_path(vault_path, idea["idea_id"])
    snapshot_ref = _paper_distill_ref(vault_path, snapshot_path)
    memo_frontmatter = _build_memo_frontmatter(
        idea=idea,
        snapshot=persisted_snapshot,
        snapshot_ref=snapshot_ref,
        promoted=promoted,
    )
    memo_body = _build_memo_body(
        idea=idea,
        snapshot=persisted_snapshot,
        snapshot_ref=snapshot_ref,
    )
    try:
        write_markdown(memo_path, memo_frontmatter, memo_body)
    except OSError as exc:
        return _failure_result(
            mutation_id=mutation["id"],
            idea_id=idea["idea_id"],
            error=f"Failed to write idea memo {idea['idea_id']}: {exc}",
            verification_state=persisted_snapshot["verification_state"],
            snapshot_persisted=True,
            snapshot_path=str(snapshot_path),
            snapshot_id=persisted_snapshot["snapshot_id"],
            idea_path=str(memo_path),
        )

    return _success_result(
        mutation_id=mutation["id"],
        idea_id=idea["idea_id"],
        idea_path=str(memo_path),
        snapshot_path=str(snapshot_path),
        snapshot_id=persisted_snapshot["snapshot_id"],
        verification_state=persisted_snapshot["verification_state"],
        promoted=promoted,
        provider_summary=dict(
            persisted_snapshot.get("external_verification", {}).get("provider_summary") or {}
        ),
        missing_providers=list(
            persisted_snapshot.get("external_verification", {}).get("missing_providers") or []
        ),
        promotion_block_reason=persisted_snapshot.get("promotion_block_reason"),
    )


def _normalize_verify_result(result: dict[str, Any], *, idea_id: str) -> dict[str, Any]:
    normalized = dict(result)
    normalized.setdefault("idea_id", idea_id)

    if "idea_write_state" not in normalized:
        return _failure_result(
            mutation_id=normalized.get("mutation_id"),
            idea_id=idea_id,
            error=str(normalized.get("error") or "idea verification failed"),
            verification_state=str(normalized.get("verification_state") or "unknown"),
            snapshot_persisted=bool(normalized.get("snapshot_persisted")),
            snapshot_path=normalized.get("snapshot_path"),
            snapshot_id=normalized.get("snapshot_id"),
            idea_path=normalized.get("idea_path"),
        )

    normalized.setdefault("snapshot_write_state", "persisted" if normalized.get("snapshot_persisted") else "failed")
    normalized.setdefault("promoted", False)
    normalized.setdefault("promotion_blocked", not normalized["promoted"])
    if normalized["promoted"]:
        normalized.setdefault("idea_state", "durable")
    else:
        normalized.setdefault("idea_state", "draft" if normalized.get("ok") else "unchanged")
    normalized.setdefault("provider_summary", {})
    normalized.setdefault("missing_providers", [])
    normalized.setdefault("promotion_block_reason", None if normalized["promoted"] else "verification_not_satisfied")
    return normalized


def _success_result(
    *,
    mutation_id: int,
    idea_id: str,
    idea_path: str,
    snapshot_path: str,
    snapshot_id: str,
    verification_state: str,
    promoted: bool,
    provider_summary: dict[str, Any],
    missing_providers: list[str],
    promotion_block_reason: str | None,
) -> dict[str, Any]:
    return {
        "ok": True,
        "mutation_id": mutation_id,
        "idea_id": idea_id,
        "idea_path": idea_path,
        "snapshot_path": snapshot_path,
        "snapshot_id": snapshot_id,
        "snapshot_persisted": True,
        "snapshot_write_state": "persisted",
        "idea_write_state": "durable_saved" if promoted else "draft_saved",
        "idea_state": "durable" if promoted else "draft",
        "verification_state": verification_state,
        "promoted": promoted,
        "promotion_blocked": not promoted,
        "promotion_block_reason": None if promoted else promotion_block_reason,
        "provider_summary": provider_summary,
        "missing_providers": missing_providers,
    }


def _failure_result(
    *,
    mutation_id: int | None,
    idea_id: str | None,
    error: str,
    verification_state: str,
    snapshot_persisted: bool,
    snapshot_path: str | None = None,
    snapshot_id: str | None = None,
    idea_path: str | None = None,
) -> dict[str, Any]:
    return {
        "ok": False,
        "mutation_id": mutation_id,
        "idea_id": idea_id,
        "idea_path": idea_path,
        "snapshot_path": snapshot_path,
        "snapshot_id": snapshot_id,
        "snapshot_persisted": snapshot_persisted,
        "snapshot_write_state": "persisted" if snapshot_persisted else "failed",
        "idea_write_state": "failed",
        "idea_state": "unchanged",
        "verification_state": verification_state,
        "promoted": False,
        "promotion_blocked": True,
        "promotion_block_reason": "snapshot_write_failed" if not snapshot_persisted else "memo_write_failed",
        "provider_summary": {},
        "missing_providers": [],
        "error": error,
    }


def _materialize_snapshot(
    mutation: dict[str, Any],
    idea: dict[str, Any],
    verification: dict[str, Any],
) -> dict[str, Any]:
    created_at = str(mutation.get("created_at") or _now_iso())
    verification_state = verification["verification_state"]
    return {
        "schema_version": _SCHEMA_VERSION,
        "snapshot_id": _snapshot_id_for_mutation(mutation),
        "mutation_id": mutation["id"],
        "created_at": created_at,
        "idea": {
            "idea_id": idea["idea_id"],
            "title": idea["title"],
            "summary": idea["summary"],
            "hypothesis": idea["hypothesis"],
            "local_evidence": idea["local_evidence"],
        },
        "trust_context": {
            "order": ["wiki", "sources", "memory", "external"],
            "wiki": "canonical_local_knowledge",
            "sources": "approved_local_evidence",
            "memory": "advisory_local_memory",
            "external": "challenge_layer",
        },
        "external_verification": {
            "queries": list(verification["queries"]),
            "required_providers": list(verification["required_providers"]),
            "missing_providers": list(verification["missing_providers"]),
            "provider_summary": dict(verification["provider_summary"]),
            "providers": list(verification["providers"]),
            "contradictions": list(verification["contradictions"]),
            "notes": verification["notes"],
        },
        "verification_state": verification_state,
        "promotion_eligible": verification_state == "verified",
        "promotion_block_reason": _promotion_block_reason(verification_state),
    }


def _build_memo_frontmatter(
    *,
    idea: dict[str, Any],
    snapshot: dict[str, Any],
    snapshot_ref: str,
    promoted: bool,
) -> dict[str, Any]:
    external = snapshot.get("external_verification", {})
    provider_summary = external.get("provider_summary", {})
    return {
        "type": "idea-memo",
        "section": "insights/ideas",
        "idea_id": idea["idea_id"],
        "title": idea["title"],
        "idea_state": "durable" if promoted else "draft",
        "verification_state": snapshot["verification_state"],
        "verified": promoted,
        "updated": snapshot["created_at"],
        "verification_snapshot": snapshot_ref,
        "required_providers": list(external.get("required_providers") or []),
        "missing_providers": list(external.get("missing_providers") or []),
        "providers_succeeded": list(provider_summary.get("succeeded") or []),
        "providers_failed": list(provider_summary.get("failed") or []),
        "providers_partial": list(provider_summary.get("partial") or []),
        "providers_contradicted": list(provider_summary.get("contradicted") or []),
        "promotion_block_reason": None if promoted else snapshot.get("promotion_block_reason"),
        "trust_order": ["wiki", "sources", "memory", "external"],
    }


def _build_memo_body(
    *,
    idea: dict[str, Any],
    snapshot: dict[str, Any],
    snapshot_ref: str,
) -> str:
    external = snapshot.get("external_verification", {})
    provider_summary = external.get("provider_summary", {})
    lines = [
        f"# {idea['title']}",
        "",
        "## Summary",
        "",
        idea["summary"],
    ]

    if idea["hypothesis"]:
        lines.extend(
            [
                "",
                "## Hypothesis",
                "",
                idea["hypothesis"],
            ]
        )

    lines.extend(
        [
            "",
            "## Local Evidence",
            "",
            "Trust order in this memo stays fixed: wiki, sources, memory, then external challenge.",
        ]
    )
    for layer in _LAYER_ORDER:
        lines.extend(["", f"### {layer.title()}", ""])
        entries = idea["local_evidence"].get(layer) or []
        if not entries:
            lines.append("- None captured.")
            continue
        for item in entries:
            lines.append(f"- {_format_evidence_item(item)}")

    lines.extend(
        [
            "",
            "## External Verification",
            "",
            f"- Verification state: {snapshot['verification_state']}",
            f"- Snapshot: {snapshot_ref}",
            f"- Required providers: {', '.join(external.get('required_providers') or []) or 'none'}",
            f"- Missing providers: {', '.join(external.get('missing_providers') or []) or 'none'}",
            f"- Providers succeeded: {', '.join(provider_summary.get('succeeded') or []) or 'none'}",
            f"- Providers failed: {', '.join(provider_summary.get('failed') or []) or 'none'}",
            f"- Providers partial: {', '.join(provider_summary.get('partial') or []) or 'none'}",
            f"- Providers contradicted: {', '.join(provider_summary.get('contradicted') or []) or 'none'}",
        ]
    )

    contradictions = list(external.get("contradictions") or [])
    if contradictions:
        lines.extend(["", "### Contradictions", ""])
        for item in contradictions:
            lines.append(f"- {_format_evidence_item(item)}")

    notes = str(external.get("notes") or "").strip()
    if notes:
        lines.extend(["", "### Verification Notes", "", notes])

    return "\n".join(lines).strip()


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


def _promotion_block_reason(verification_state: str) -> str | None:
    if verification_state == "verified":
        return None
    if verification_state == "provider_failed":
        return "provider_failed"
    if verification_state == "partial":
        return "partial_evidence"
    if verification_state == "contradicted":
        return "contradiction_detected"
    return "verification_not_satisfied"


def _format_evidence_item(item: dict[str, str]) -> str:
    label = (
        item.get("ref")
        or item.get("title")
        or item.get("view_key")
        or "evidence"
    )
    extras = [
        item.get("summary") or "",
        item.get("excerpt") or "",
    ]
    detail = " ".join(part for part in extras if part).strip()
    if detail:
        return f"{label} - {detail}"
    return str(label)


def _snapshot_id_for_mutation(mutation: dict[str, Any]) -> str:
    return f"idea-verification-{int(mutation['id']):08d}"


def _snapshot_path_for_mutation(vault_path: str, mutation: dict[str, Any], idea_id: str) -> Path:
    created_at = str(mutation.get("created_at") or _now_iso())
    day = created_at.split("T", 1)[0] if "T" in created_at else created_at[:10]
    return root_path(vault_path, "verification") / day / f"{idea_id}-{_snapshot_id_for_mutation(mutation)}.json"


def _idea_memo_path(vault_path: str, idea_id: str) -> Path:
    return root_path(vault_path, "ideas") / f"{idea_id}.md"


def _paper_distill_ref(vault_path: str, path: Path) -> str:
    root = paper_distill_root(vault_path)
    return f"Paper Distill/{path.relative_to(root).as_posix()}"


def _atomic_write_json(path: Path, payload: dict[str, Any]) -> None:
    assert_supported_write_path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = path.with_name(f".{path.name}.{uuid.uuid4().hex}.tmp")
    tmp_path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    os.replace(tmp_path, path)


def _read_snapshot_file(path: Path) -> dict[str, Any]:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise VerificationSnapshotPersistError(f"Verification snapshot is corrupt: {path}") from exc


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
