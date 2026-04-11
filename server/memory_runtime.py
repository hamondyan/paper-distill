"""Event-first memory storage with read-time overlay support.

Memory writes append immutable events under ``.state/memory/events`` directly.
Current views under ``memory/`` remain advisory compiled read models and are
never rewritten directly by append-time flows.
"""
from __future__ import annotations

import json
import os
import re
import threading
import uuid
from pathlib import Path
from typing import Any

import yaml

from server.database import _now_iso
from server.memory_contract import (
    order_memory_view_keys,
    public_memory_view_contract,
    validate_typed_memory_event,
)
from server.memory_promotion import (
    collapse_promoted_memory_events,
    validate_memory_promotion_boundary,
)
from server.vault_contract import root_path
from server.vault_ops import ensure_vault_structure

_VIEW_KEY_RE = re.compile(r"^[a-z0-9][a-z0-9_-]*$")
_EVENT_SCHEMA_VERSION = "2026-04-09"
_event_id_guard = threading.Lock()
_event_id_counter = 0


class MemoryEventPersistError(RuntimeError):
    """Raised when a durable memory event cannot be written."""


class MemoryEventValidationError(ValueError):
    """Raised when an incoming memory event is missing required structure."""


def append_memory_event(
    vault_path: str,
    *,
    event: dict[str, Any],
    created_at: str | None = None,
) -> dict[str, Any]:
    """Append a durable memory event directly into the hidden event store."""
    try:
        normalized = _normalize_event_request(event)
    except MemoryEventValidationError as exc:
        return {
            "ok": False,
            "memory_write_state": "failed",
            "appended": False,
            "remembered": False,
            "compiled": False,
            "overlay_available": False,
            "error": str(exc),
        }

    try:
        persisted, event_path = _persist_memory_event(
            vault_path,
            normalized,
            created_at=created_at,
        )
    except MemoryEventPersistError as exc:
        return {
            "ok": False,
            "memory_write_state": "failed",
            "appended": False,
            "remembered": False,
            "compiled": False,
            "overlay_available": False,
            "error": str(exc),
        }
    return _append_result_from_event(persisted, event_path)


def list_uncompiled_memory_events(
    vault_path: str,
    *,
    view_keys: list[str] | None = None,
    limit: int | None = None,
) -> list[dict[str, Any]]:
    """Return persisted memory events that still need memory-compile."""
    return list_memory_events(
        vault_path,
        only_uncompiled=True,
        view_keys=view_keys,
        limit=limit,
    )


def list_memory_events(
    vault_path: str,
    *,
    only_uncompiled: bool = False,
    view_keys: list[str] | None = None,
    limit: int | None = None,
) -> list[dict[str, Any]]:
    """Return persisted memory events ordered newest-first."""
    ensure_vault_structure(vault_path)
    requested = _normalize_requested_view_keys(view_keys)
    events: list[dict[str, Any]] = []

    for path in sorted(_events_root(vault_path).rglob("*.json")):
        event = _read_event_file(path)
        event["event_path"] = str(path)

        if requested and not set(event.get("view_keys", [])).intersection(requested):
            continue
        if only_uncompiled and not _event_has_uncompiled_requested_views(event, requested):
            continue
        events.append(event)

    events.sort(
        key=lambda item: (
            str(item.get("created_at") or ""),
            str(item.get("event_id") or ""),
        ),
        reverse=True,
    )
    if limit is not None and limit >= 0:
        return events[:limit]
    return events


def read_memory_views(
    vault_path: str,
    *,
    view_keys: list[str] | None = None,
    overlay_limit: int = 20,
) -> dict[str, Any]:
    """Read compiled memory views and overlay recent uncompiled events."""
    ensure_vault_structure(vault_path)
    requested = _normalize_requested_view_keys(view_keys)
    compiled_views = _load_compiled_views(vault_path, requested)
    overlay_events = collapse_promoted_memory_events(
        list_uncompiled_memory_events(
        vault_path,
        view_keys=requested,
        limit=overlay_limit,
        )
    )

    ordered_view_keys = _ordered_view_keys(
        requested=requested,
        compiled=compiled_views,
        overlay_events=overlay_events,
    )
    views: dict[str, Any] = {}
    for view_key in ordered_view_keys:
        compiled = compiled_views.get(view_key, {})
        matching_events = [
            _public_event_shape(event)
            for event in overlay_events
            if _event_has_uncompiled_view_key(event, view_key)
        ]
        views[view_key] = {
            "view_key": view_key,
            "compiled": bool(compiled),
            "path": compiled.get("path"),
            "frontmatter": compiled.get("frontmatter", {}),
            "body": compiled.get("body", ""),
            "contract": public_memory_view_contract(view_key),
            "overlay_events": matching_events,
            "overlay_count": len(matching_events),
        }

    result = {
        "overlay_applied": bool(overlay_events),
        "uncompiled_event_count": len(overlay_events),
        "views": views,
    }
    _maybe_opportunistic_compile(vault_path, requested)
    return result


def _append_result_from_event(event: dict[str, Any], event_path: Path) -> dict[str, Any]:
    return {
        "ok": True,
        "memory_write_state": "event_appended",
        "appended": True,
        "remembered": True,
        "compiled": False,
        "overlay_available": True,
        "event_id": event["event_id"],
        "event_path": str(event_path),
        "event": _public_event_shape(event),
    }


def _persist_memory_event(
    vault_path: str,
    event: dict[str, Any],
    *,
    created_at: str | None = None,
    event_id: str | None = None,
) -> tuple[dict[str, Any], Path]:
    ensure_vault_structure(vault_path)
    created = str(created_at or _now_iso())
    persisted_event_id = str(event_id or _event_id_for_now(created))
    event_path = _event_path(vault_path, created, persisted_event_id)

    if event_path.exists():
        persisted = _read_event_file(event_path)
        return persisted, event_path

    persisted = _materialize_event_record(
        event=event,
        created_at=created,
        event_id=persisted_event_id,
    )
    try:
        _atomic_write_json(event_path, persisted)
    except OSError as exc:
        raise MemoryEventPersistError(
            f"Failed to append memory event {persisted_event_id}: {exc}"
        ) from exc
    return persisted, event_path


def _public_event_shape(event: dict[str, Any]) -> dict[str, Any]:
    return {
        "event_id": event.get("event_id"),
        "created_at": event.get("created_at"),
        "event_type": event.get("event_type"),
        "title": event.get("title"),
        "summary": event.get("summary"),
        "content": event.get("content"),
        "view_keys": list(event.get("view_keys") or []),
        "trust_label": event.get("trust_label"),
        "status": event.get("status"),
        "source": dict(event.get("source") or {}),
        "metadata": dict(event.get("metadata") or {}),
        "compile_status": event.get("compile_status"),
        "compiled_at": event.get("compiled_at"),
        "compiled_view_keys": list(event.get("compiled_view_keys") or []),
    }


def _materialize_event_record(
    *,
    event: dict[str, Any],
    created_at: str,
    event_id: str,
) -> dict[str, Any]:
    return {
        "schema_version": _EVENT_SCHEMA_VERSION,
        "event_id": event_id,
        "created_at": created_at,
        "event_type": event["event_type"],
        "title": event["title"],
        "summary": event["summary"],
        "content": event.get("content", ""),
        "view_keys": list(event["view_keys"]),
        "trust_label": event["trust_label"],
        "status": event["status"],
        "source": dict(event.get("source") or {}),
        "metadata": dict(event.get("metadata") or {}),
        "compile_status": "pending",
        "compiled_at": None,
        "compiled_view_keys": [],
    }


def _event_path(vault_path: str, created_at: str, event_id: str) -> Path:
    day = created_at.split("T", 1)[0] if "T" in created_at else created_at[:10]
    return _events_root(vault_path) / day / f"{event_id}.json"


def _normalize_event_request(event: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(event, dict):
        raise MemoryEventValidationError("Memory event payload must be an object.")

    event_type = str(event.get("event_type") or "").strip()
    if not event_type:
        raise MemoryEventValidationError("Memory event requires non-empty event_type.")

    summary = str(event.get("summary") or "").strip()
    if not summary:
        raise MemoryEventValidationError("Memory event requires non-empty summary.")

    trust_label = str(event.get("trust_label") or "").strip()
    if not trust_label:
        raise MemoryEventValidationError("Memory event requires non-empty trust_label.")

    view_keys = _normalize_requested_view_keys(
        event.get("view_keys")
        if event.get("view_keys") is not None
        else ([event.get("view_key")] if event.get("view_key") is not None else None)
    )
    if not view_keys:
        raise MemoryEventValidationError("Memory event requires at least one view_key.")

    title = str(event.get("title") or "").strip() or summary[:120]
    status = str(event.get("status") or "provisional").strip() or "provisional"

    normalized: dict[str, Any] = {
        "event_type": event_type,
        "title": title,
        "summary": summary,
        "content": str(event.get("content") or "").strip(),
        "view_keys": view_keys,
        "trust_label": trust_label,
        "status": status,
        "source": dict(event.get("source") or {}),
        "metadata": dict(event.get("metadata") or {}),
    }
    try:
        validate_typed_memory_event(normalized)
        validate_memory_promotion_boundary(normalized)
    except ValueError as exc:
        raise MemoryEventValidationError(str(exc)) from exc
    return normalized


def _normalize_requested_view_keys(view_keys: Any) -> list[str]:
    if view_keys is None:
        return []
    if isinstance(view_keys, str):
        candidate_keys = [view_keys]
    else:
        candidate_keys = list(view_keys)

    normalized: list[str] = []
    seen: set[str] = set()
    for raw_key in candidate_keys:
        key = str(raw_key or "").strip()
        if not key:
            continue
        if not _VIEW_KEY_RE.match(key):
            raise MemoryEventValidationError(f"Invalid memory view key: {key}")
        if key not in seen:
            seen.add(key)
            normalized.append(key)
    return normalized


def _events_root(vault_path: str) -> Path:
    return root_path(vault_path, "state_memory") / "events"


def _event_id_for_now(created_at: str) -> str:
    stamp = re.sub(r"[^0-9]", "", created_at)[:14] or "event"
    global _event_id_counter
    with _event_id_guard:
        _event_id_counter += 1
        suffix = _event_id_counter
    return f"memory-event-{stamp}-{suffix:08d}"


def _atomic_write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = path.with_name(f".{path.name}.{uuid.uuid4().hex}.tmp")
    tmp_path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    os.replace(tmp_path, path)


def _read_event_file(path: Path) -> dict[str, Any]:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise MemoryEventPersistError(f"Memory event file is corrupt: {path}") from exc


def _load_compiled_views(
    vault_path: str,
    requested: list[str],
) -> dict[str, dict[str, Any]]:
    memory_dir = root_path(vault_path, "memory")
    views: dict[str, dict[str, Any]] = {}
    for path in sorted(memory_dir.glob("*.md")):
        if path.name == "_index.md":
            continue
        frontmatter, body = _read_markdown_frontmatter(path)
        view_key = str(frontmatter.get("view_key") or path.stem).strip()
        if requested and view_key not in requested:
            continue
        views[view_key] = {
            "view_key": view_key,
            "path": str(path),
            "frontmatter": frontmatter,
            "body": body,
        }
    return views


def _read_markdown_frontmatter(path: Path) -> tuple[dict[str, Any], str]:
    content = path.read_text(encoding="utf-8")
    if not content.startswith("---\n"):
        return {}, content.strip()

    try:
        _, remainder = content.split("---\n", 1)
        fm_text, body = remainder.split("\n---\n", 1)
    except ValueError:
        return {}, content.strip()

    frontmatter = yaml.safe_load(fm_text) or {}
    if not isinstance(frontmatter, dict):
        frontmatter = {}
    return frontmatter, body.strip()


def _ordered_view_keys(
    *,
    requested: list[str],
    compiled: dict[str, dict[str, Any]],
    overlay_events: list[dict[str, Any]],
) -> list[str]:
    ordered: list[str] = []
    seen: set[str] = set()

    def _push(key: str) -> None:
        if key and key not in seen:
            seen.add(key)
            ordered.append(key)

    for key in requested:
        _push(key)
    for key in compiled:
        _push(key)
    for event in overlay_events:
        for key in event.get("view_keys", []):
            if _event_has_uncompiled_view_key(event, str(key)):
                _push(str(key))
    return order_memory_view_keys(ordered)


def _event_has_uncompiled_requested_views(event: dict[str, Any], requested: list[str]) -> bool:
    event_keys = set(event.get("view_keys") or [])
    compiled_keys = set(event.get("compiled_view_keys") or [])
    relevant = event_keys if not requested else event_keys.intersection(requested)
    return bool(relevant - compiled_keys)


def _event_has_uncompiled_view_key(event: dict[str, Any], view_key: str) -> bool:
    event_keys = set(event.get("view_keys") or [])
    compiled_keys = set(event.get("compiled_view_keys") or [])
    return view_key in event_keys and view_key not in compiled_keys


def _maybe_opportunistic_compile(vault_path: str, requested: list[str]) -> None:
    if not requested:
        return

    pending = list_uncompiled_memory_events(vault_path, view_keys=requested, limit=1)
    if not pending:
        return

    try:
        from server.memory_compile import compile_memory_views

        compile_memory_views(vault_path, view_keys=requested)
    except Exception:
        return
