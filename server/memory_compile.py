"""Deterministic compiler for advisory memory current views.

Wave 2 starts from the verified Wave 1 contract:
- memory writes remain event-first under ``.state/memory/events``
- reads keep overlay fallback for fresh uncompiled events
- ``memory-compile`` only builds current views under ``memory/``

This module intentionally keeps synthesis explicit and deterministic. It groups
pending events by view key, renders markdown current views, and marks only the
published event/view pairs as compiled.
"""
from __future__ import annotations

import json
import os
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any

import yaml

from server.active_threads import build_active_thread_snapshot
from server.memory_consolidation import consolidate_memory_events
from server.memory_contract import (
    build_memory_view_frontmatter,
    get_memory_view_spec,
    order_memory_view_keys,
)
from server.memory_promotion import collapse_promoted_memory_events
from server.memory_runtime import (
    MemoryEventPersistError,
    MemoryEventValidationError,
    _normalize_requested_view_keys,
    list_memory_events,
    list_uncompiled_memory_events,
)
from server.vault_contract import root_path
from server.vault_ops import ensure_vault_structure


class MemorySynthesisError(RuntimeError):
    """Raised when a compiled memory view cannot be rendered or persisted."""


def compile_memory_views(
    vault_path: str,
    *,
    view_keys: list[str] | None = None,
) -> dict[str, Any]:
    """Compile pending memory events directly into current views."""
    try:
        normalized_keys = _normalize_requested_view_keys(view_keys)
    except MemoryEventValidationError as exc:
        return {
            "ok": False,
            "compiled": False,
            "compiled_view_keys": [],
            "compiled_event_count": 0,
            "error": str(exc),
        }

    return _commit_memory_compile(vault_path, normalized_keys)


def _target_key(view_keys: list[str]) -> str:
    if not view_keys:
        return "memory:compile:all"
    return "memory:compile:" + ",".join(sorted(view_keys))


def _commit_memory_compile(
    vault_path: str,
    requested: list[str],
) -> dict[str, Any]:
    ensure_vault_structure(vault_path)
    bundle = _build_memory_compile_bundle(vault_path, requested)
    if not bundle.get("compiled"):
        return dict(bundle)

    try:
        _apply_memory_compile_bundle(vault_path, bundle)
    except Exception as exc:
        return {
            "ok": False,
            "compiled": False,
            "compiled_view_keys": [],
            "compiled_event_count": 0,
            "error": str(exc),
        }

    return _result_from_bundle(bundle)


def _build_memory_compile_bundle(vault_path: str, requested: list[str]) -> dict[str, Any]:
    pending_events = list_uncompiled_memory_events(vault_path, view_keys=requested or None)
    compile_view_keys = _pending_view_keys(pending_events, requested)
    if not compile_view_keys:
        return {
            "ok": True,
            "compiled": False,
            "compiled_view_keys": [],
            "compiled_event_count": 0,
            "reason": "no_pending_events",
        }

    compiled_at = datetime.now().isoformat(timespec="seconds")
    all_events = list_memory_events(vault_path, view_keys=compile_view_keys)
    files: list[dict[str, str]] = []
    view_paths: dict[str, str] = {}

    for view_key in compile_view_keys:
        relevant_events = [event for event in all_events if view_key in set(event.get("view_keys", []))]
        markdown = _render_view_markdown(
            view_key=view_key,
            events=relevant_events,
            compiled_at=compiled_at,
        )
        dest = root_path(vault_path, "memory") / f"{view_key}.md"
        files.append(
            {
                "dest_relpath": str(dest.relative_to(Path(vault_path))),
                "content": markdown,
            }
        )
        view_paths[view_key] = str(dest)

    compiled_event_ids: list[str] = []
    for event in pending_events:
        updated = _updated_event_payload(event, compile_view_keys, compiled_at)
        if updated is None:
            continue
        event_path = Path(str(event["event_path"]))
        files.append(
            {
                "dest_relpath": str(event_path.relative_to(Path(vault_path))),
                "content": json.dumps(updated, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
            }
        )
        compiled_event_ids.append(str(updated.get("event_id") or ""))

    return {
        "compiled": True,
        "files": files,
        "result": {
            "ok": True,
            "compiled": True,
            "compiled_view_keys": compile_view_keys,
            "compiled_event_count": len(compiled_event_ids),
            "compiled_event_ids": compiled_event_ids,
            "view_paths": view_paths,
        },
    }


def _pending_view_keys(events: list[dict[str, Any]], requested: list[str]) -> list[str]:
    seen: set[str] = set()
    ordered: list[str] = []
    for event in events:
        event_keys = set(event.get("view_keys") or [])
        compiled_keys = set(event.get("compiled_view_keys") or [])
        relevant = event_keys if not requested else event_keys.intersection(requested)
        for key in sorted(relevant - compiled_keys):
            if key not in seen:
                seen.add(key)
                ordered.append(key)
    return order_memory_view_keys(ordered)


def _updated_event_payload(
    event: dict[str, Any],
    compile_view_keys: list[str],
    compiled_at: str,
) -> dict[str, Any] | None:
    event_keys = set(event.get("view_keys") or [])
    compiled_keys = set(event.get("compiled_view_keys") or [])
    newly_compiled = event_keys.intersection(compile_view_keys) - compiled_keys
    if not newly_compiled:
        return None

    updated = dict(event)
    updated.pop("event_path", None)
    next_compiled = sorted(compiled_keys.union(newly_compiled))
    updated["compiled_view_keys"] = next_compiled
    updated["compiled_at"] = compiled_at
    updated["compile_status"] = (
        "compiled" if set(next_compiled) == event_keys else "partial"
    )
    return updated


def _render_view_markdown(
    *,
    view_key: str,
    events: list[dict[str, Any]],
    compiled_at: str,
) -> str:
    visible_events = collapse_promoted_memory_events(events)
    consolidation = consolidate_memory_events(view_key, visible_events)
    frontmatter = build_memory_view_frontmatter(
        view_key,
        compiled_at=compiled_at,
        compiled_event_count=len(visible_events),
    )
    frontmatter["compiled_item_count"] = consolidation["item_count"]
    frontmatter["stale_item_count"] = consolidation["stale_item_count"]
    frontmatter["retired_item_count"] = consolidation["retired_item_count"]
    title = _view_title(view_key)
    intro = _view_intro(view_key)

    if view_key == "active-threads":
        snapshot = build_active_thread_snapshot(visible_events)
        frontmatter["active_thread_count"] = snapshot["active_thread_count"]
        frontmatter["inactive_thread_count"] = snapshot["inactive_thread_count"]
        return _render_active_threads_markdown(
            frontmatter=frontmatter,
            title=title,
            intro=intro,
            snapshot=snapshot,
        )

    lines = [
        _frontmatter_block(frontmatter),
        "",
        f"# {title}",
        "",
        intro,
        "",
    ]
    items = list(consolidation.get("items") or [])
    current_items = [
        item for item in items if str(item.get("effective_status") or "") not in {"stale", "retired", "rejected"}
    ]
    lower_salience_items = [
        item for item in items if str(item.get("effective_status") or "") in {"stale", "retired", "rejected"}
    ]

    if not items:
        lines.extend(
            [
                "No memory events have been compiled into this view yet.",
                "",
            ]
        )
        return "\n".join(lines).strip() + "\n"

    lines.extend(
        [
            "## Current Signals",
            "",
        ]
    )
    if not current_items:
        lines.extend(
            [
                "No high-salience memory signals are currently active in this view.",
                "",
            ]
        )
    else:
        for item in current_items:
            lines.append(_render_consolidated_item_line(item))
            content = str(item.get("content") or "").strip()
            if content:
                lines.append(f"  {content}")
            if int(item.get("support_count") or 0) > 1:
                lines.append(
                    f"  Supporting events: {int(item.get('support_count') or 0)}"
                )
            recent_summaries = list(item.get("recent_summaries") or [])
            if len(recent_summaries) > 1:
                lines.append("  Recent supporting summaries:")
                for summary in recent_summaries:
                    lines.append(f"    - {summary}")
            lines.append("")

    if lower_salience_items:
        lines.extend(
            [
                "## Lower-Salience Memory",
                "",
            ]
        )
        for item in lower_salience_items:
            lines.append(_render_consolidated_item_line(item))
            content = str(item.get("content") or "").strip()
            if content:
                lines.append(f"  {content}")
            lines.append("")
    lines.append("")
    return "\n".join(lines).strip() + "\n"


def _render_active_threads_markdown(
    *,
    frontmatter: dict[str, Any],
    title: str,
    intro: str,
    snapshot: dict[str, Any],
) -> str:
    active_threads = list(snapshot.get("active_threads") or [])
    inactive_threads = list(snapshot.get("inactive_threads") or [])

    lines = [
        _frontmatter_block(frontmatter),
        "",
        f"# {title}",
        "",
        intro,
        "",
        "## Current Active Threads",
        "",
    ]

    if not active_threads:
        lines.extend(
            [
                "No threads are currently active in this compiled view.",
                "",
            ]
        )
    else:
        for thread in active_threads:
            lines.extend(
                [
                    f"### {thread['title']}",
                    "",
                    f"- Thread ID: {thread['thread_id']}",
                    f"- Lifecycle: active ({thread['last_action']})",
                    f"- Status: {thread['status']}",
                    f"- Trust: {thread['trust_label']}",
                    f"- Entered: {thread['entered_at'] or 'unknown'}",
                    f"- Last updated: {thread['last_updated_at'] or 'unknown'}",
                    f"- Compiled events: {thread['event_count']}",
                    "",
                    str(thread.get("summary") or "").strip() or "No summary recorded.",
                ]
            )
            content = str(thread.get("content") or "").strip()
            if content:
                lines.extend(["", content])
            updates = list(thread.get("updates") or [])
            if len(updates) > 1:
                lines.extend(["", "Recent updates:"])
                for update in updates:
                    lines.append(f"- {update}")
            lines.append("")

    if inactive_threads:
        lines.extend(
            [
                "## Recently Closed or Dormant",
                "",
            ]
        )
        for thread in inactive_threads[:5]:
            lines.extend(
                [
                    f"- {thread['title']} ({thread['thread_id']}) | "
                    f"last action={thread['last_action']} | "
                    f"status={thread['status']} | "
                    f"updated={thread['last_updated_at'] or 'unknown'}",
                ]
            )
        lines.append("")

    return "\n".join(lines).strip() + "\n"


def _render_event_line(event: dict[str, Any]) -> str:
    created_at = str(event.get("created_at") or "")
    trust_label = str(event.get("trust_label") or "unknown")
    status = str(event.get("status") or "provisional")
    summary = str(event.get("summary") or "").strip()
    return f"- {created_at} | {trust_label} | {status} | {summary}"


def _render_consolidated_item_line(item: dict[str, Any]) -> str:
    created_at = str(item.get("latest_created_at") or "")
    trust_label = str(item.get("trust_label") or "unknown")
    status = str(item.get("effective_status") or "provisional")
    summary = str(item.get("summary") or "").strip()
    support_count = int(item.get("support_count") or 0)
    salience = float(item.get("salience") or 0.0)
    suffix = f" | support={support_count} | salience={salience:.2f}"
    return f"- {created_at} | {trust_label} | {status} | {summary}{suffix}"


def _view_title(view_key: str) -> str:
    spec = get_memory_view_spec(view_key)
    if spec is not None:
        return spec.title
    return view_key.replace("-", " ").replace("_", " ").title()


def _view_intro(view_key: str) -> str:
    spec = get_memory_view_spec(view_key)
    if spec is not None:
        return spec.description
    return "Compiled advisory memory view from persisted memory events."


def _frontmatter_block(payload: dict[str, Any]) -> str:
    dumped = yaml.safe_dump(
        payload,
        sort_keys=False,
        allow_unicode=True,
        default_flow_style=False,
    ).strip()
    return f"---\n{dumped}\n---"


def _result_from_bundle(bundle: dict[str, Any]) -> dict[str, Any]:
    result = bundle.get("result")
    if isinstance(result, dict):
        return dict(result)
    raise MemoryEventPersistError("Memory compile publish bundle is missing result metadata.")


def _apply_memory_compile_bundle(vault_path: str, bundle: dict[str, Any]) -> None:
    backups: dict[Path, str | None] = {}
    applied: list[Path] = []
    try:
        for file_spec in bundle.get("files", []):
            dest = Path(vault_path).expanduser() / str(file_spec["dest_relpath"])
            backups[dest] = dest.read_text(encoding="utf-8") if dest.exists() else None
            _atomic_write_text(dest, str(file_spec["content"]))
            applied.append(dest)
    except Exception:
        for dest in reversed(applied):
            original = backups.get(dest)
            if original is None:
                dest.unlink(missing_ok=True)
            else:
                _atomic_write_text(dest, original)
        raise


def _atomic_write_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = path.with_name(f".{path.name}.{uuid.uuid4().hex}.tmp")
    tmp_path.write_text(content, encoding="utf-8")
    os.replace(tmp_path, path)
