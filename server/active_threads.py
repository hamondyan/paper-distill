"""State helpers for the ``active-threads`` memory view.

An active thread is a named research workstream or open loop that stays visible
in the compiled current view until an explicit exit (or an inactive status)
closes it out. Event history remains append-only under ``.state/memory/events``;
this module only defines how those events are validated and folded into the
latest-state view.
"""
from __future__ import annotations

import re
from typing import Any

THREAD_ACTIONS = frozenset({"enter", "update", "exit"})
INACTIVE_THREAD_STATUSES = frozenset({"stale", "retired", "rejected"})
_THREAD_ID_RE = re.compile(r"^[a-z0-9][a-z0-9_-]*$")


def validate_active_thread_event(event: dict[str, Any]) -> None:
    """Validate active-thread metadata on a typed memory event."""
    metadata = dict(event.get("metadata") or {})

    thread_id = str(metadata.get("thread_id") or "").strip()
    if not thread_id:
        raise ValueError("Active thread memory requires metadata.thread_id.")
    if not _THREAD_ID_RE.match(thread_id):
        raise ValueError(
            "Active thread metadata.thread_id must match ^[a-z0-9][a-z0-9_-]*$."
        )

    action = str(metadata.get("thread_action") or "").strip().lower()
    if action not in THREAD_ACTIONS:
        raise ValueError(
            "Active thread memory requires metadata.thread_action to be enter, update, or exit."
        )

    title = str(
        metadata.get("thread_title") or event.get("title") or event.get("summary") or ""
    ).strip()
    if not title:
        raise ValueError(
            "Active thread memory requires a non-empty title, summary, or metadata.thread_title."
        )


def build_active_thread_snapshot(events: list[dict[str, Any]]) -> dict[str, Any]:
    """Fold event history into the current set of active and inactive threads."""
    by_thread: dict[str, dict[str, Any]] = {}

    ordered_events = sorted(
        events,
        key=lambda item: (
            str(item.get("created_at") or ""),
            str(item.get("event_id") or ""),
        ),
    )

    for event in ordered_events:
        metadata = dict(event.get("metadata") or {})
        thread_id = str(metadata.get("thread_id") or "").strip()
        action = str(metadata.get("thread_action") or "").strip().lower()
        if not thread_id or action not in THREAD_ACTIONS:
            continue

        title = str(
            metadata.get("thread_title") or event.get("title") or event.get("summary") or thread_id
        ).strip() or thread_id
        summary = str(event.get("summary") or "").strip()
        content = str(event.get("content") or "").strip()
        created_at = str(event.get("created_at") or "").strip()
        status = str(event.get("status") or "provisional").strip() or "provisional"
        trust_label = str(event.get("trust_label") or "unknown").strip() or "unknown"

        record = by_thread.get(thread_id)
        if record is None:
            record = {
                "thread_id": thread_id,
                "title": title,
                "entered_at": created_at,
                "last_updated_at": created_at,
                "last_action": action,
                "status": status,
                "trust_label": trust_label,
                "summary": summary,
                "content": content,
                "event_count": 0,
                "updates": [],
            }
            by_thread[thread_id] = record

        if action == "enter" or not record.get("entered_at"):
            record["entered_at"] = created_at

        record["title"] = title or record["title"]
        record["last_updated_at"] = created_at or record["last_updated_at"]
        record["last_action"] = action
        record["status"] = status
        record["trust_label"] = trust_label
        if summary:
            record["summary"] = summary
        if content:
            record["content"] = content
        record["event_count"] = int(record.get("event_count") or 0) + 1

        updates = list(record.get("updates") or [])
        if summary and summary not in updates:
            updates.append(summary)
        record["updates"] = updates[-3:]

    active_threads: list[dict[str, Any]] = []
    inactive_threads: list[dict[str, Any]] = []
    for record in by_thread.values():
        is_active = (
            str(record.get("last_action") or "") != "exit"
            and str(record.get("status") or "") not in INACTIVE_THREAD_STATUSES
        )
        target = active_threads if is_active else inactive_threads
        target.append(record)

    active_threads.sort(
        key=lambda item: (str(item.get("last_updated_at") or ""), item["thread_id"]),
        reverse=True,
    )
    inactive_threads.sort(
        key=lambda item: (str(item.get("last_updated_at") or ""), item["thread_id"]),
        reverse=True,
    )

    return {
        "active_threads": active_threads,
        "inactive_threads": inactive_threads,
        "active_thread_count": len(active_threads),
        "inactive_thread_count": len(inactive_threads),
    }
