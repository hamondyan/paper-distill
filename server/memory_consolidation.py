"""Deterministic consolidation and decay rules for advisory memory views."""
from __future__ import annotations

import json
import re
from datetime import datetime
from typing import Any

from server.memory_promotion import (
    HIGH_IMPACT_METADATA_KEYS,
    HIGH_IMPACT_VIEW_KEYS,
    RUNTIME_CONFIRMED_STATUSES,
    collapse_promoted_memory_events,
)

_TERM_RE = re.compile(r"[a-z0-9][a-z0-9_-]{2,}")
_STOPWORDS = {
    "about",
    "after",
    "assistant",
    "because",
    "before",
    "brief",
    "current",
    "does",
    "failure",
    "from",
    "have",
    "ideas",
    "into",
    "just",
    "memory",
    "more",
    "paper",
    "papers",
    "profile",
    "research",
    "results",
    "should",
    "signal",
    "signals",
    "summary",
    "taste",
    "that",
    "their",
    "this",
    "user",
    "view",
    "views",
    "with",
}
_SIMILARITY_THRESHOLD = 0.72
_TERMINAL_STATUSES = frozenset({"retired", "rejected"})
_LOW_SALIENCE_STATUSES = frozenset({"stale", "retired"})
_STATUS_PRIORITY = {
    "confirmed": 5,
    "consolidated": 4,
    "provisional": 3,
    "stale": 2,
    "retired": 1,
    "rejected": 0,
}
_TRUST_PRIORITY = {
    "externally-verified": 4,
    "user-stated": 3,
    "jointly-derived": 2,
    "assistant-inferred": 1,
}
_DECAY_RULES = {
    "assistant-brief": {
        "provisional_stale_days": 7,
        "confirmed_stale_days": 30,
        "consolidated_stale_days": 60,
        "retire_days": 120,
    },
    "taste": {
        "provisional_stale_days": 21,
        "confirmed_stale_days": 120,
        "consolidated_stale_days": 240,
        "retire_days": 540,
    },
    "profile": {
        "provisional_stale_days": 30,
        "confirmed_stale_days": 180,
        "consolidated_stale_days": 365,
        "retire_days": 730,
    },
    "killed-ideas": {
        "provisional_stale_days": 60,
        "confirmed_stale_days": 180,
        "consolidated_stale_days": 365,
        "retire_days": 730,
    },
}
_DEFAULT_DECAY_RULES = {
    "provisional_stale_days": 30,
    "confirmed_stale_days": 180,
    "consolidated_stale_days": 365,
    "retire_days": 730,
}


def consolidate_memory_events(
    view_key: str,
    events: list[dict[str, Any]],
    *,
    now: datetime | None = None,
) -> dict[str, Any]:
    """Collapse raw memory events into current items with decay-aware status."""
    visible_events = collapse_promoted_memory_events(events)
    groups: list[dict[str, Any]] = []

    for event in sorted(visible_events, key=_chronological_key):
        signature = _event_signature(view_key, event)
        terms = _event_terms(event)
        group = _find_group(groups, signature=signature, terms=terms)
        if group is None:
            group = {
                "signature": signature,
                "terms": set(terms),
                "events": [],
            }
            groups.append(group)
        else:
            group["terms"].update(terms)
        group["events"].append(event)

    items = [_build_consolidated_item(view_key, group["events"], now=now) for group in groups]
    items.sort(
        key=lambda item: (
            float(item.get("salience") or 0.0),
            str(item.get("latest_created_at") or ""),
            str(item.get("item_key") or ""),
        ),
        reverse=True,
    )
    return {
        "items": items,
        "source_event_count": len(visible_events),
        "item_count": len(items),
        "active_item_count": len(
            [item for item in items if str(item.get("effective_status") or "") not in _LOW_SALIENCE_STATUSES]
        ),
        "stale_item_count": len(
            [item for item in items if str(item.get("effective_status") or "") == "stale"]
        ),
        "retired_item_count": len(
            [item for item in items if str(item.get("effective_status") or "") in _TERMINAL_STATUSES]
        ),
    }


def runtime_effective_memory_items(
    view_key: str,
    events: list[dict[str, Any]],
    *,
    now: datetime | None = None,
) -> list[dict[str, Any]]:
    """Return consolidated memory items that should actively shape runtime behavior."""
    snapshot = consolidate_memory_events(view_key, events, now=now)
    items = list(snapshot.get("items") or [])
    if view_key in HIGH_IMPACT_VIEW_KEYS:
        return [
            item
            for item in items
            if str(item.get("effective_status") or "") in RUNTIME_CONFIRMED_STATUSES
            and float(item.get("salience") or 0.0) >= 0.5
        ]
    return [
        item
        for item in items
        if str(item.get("effective_status") or "") not in {"retired"}
        and float(item.get("salience") or 0.0) >= 0.2
    ]


def runtime_effective_memory_events(
    view_key: str,
    events: list[dict[str, Any]],
    *,
    now: datetime | None = None,
) -> list[dict[str, Any]]:
    """Back-compat event-like surface for callers that still expect events."""
    items = runtime_effective_memory_items(view_key, events, now=now)
    normalized: list[dict[str, Any]] = []
    for item in items:
        normalized.append(
            {
                "event_id": item.get("representative_event_id"),
                "created_at": item.get("latest_created_at"),
                "event_type": item.get("representative_event_type"),
                "title": item.get("title"),
                "summary": item.get("summary"),
                "content": item.get("content"),
                "view_keys": [view_key],
                "trust_label": item.get("trust_label"),
                "status": item.get("effective_status"),
                "metadata": dict(item.get("metadata") or {}),
            }
        )
    return normalized


def classify_memory_status_decay(
    view_key: str,
    *,
    base_status: str,
    latest_created_at: str,
    support_count: int,
    has_confirmed_support: bool,
    now: datetime | None = None,
) -> str:
    normalized_status = str(base_status or "provisional").strip() or "provisional"
    if normalized_status in _TERMINAL_STATUSES:
        return normalized_status

    age_days = _age_in_days(latest_created_at, now=now)
    rules = _DECAY_RULES.get(view_key, _DEFAULT_DECAY_RULES)

    effective_status = normalized_status
    if (
        effective_status in {"confirmed", "consolidated"}
        and support_count > 1
        and has_confirmed_support
    ):
        effective_status = "consolidated"

    if effective_status == "stale":
        if age_days >= int(rules["retire_days"]):
            return "retired"
        return "stale"

    stale_days = int(
        rules["provisional_stale_days"]
        if effective_status == "provisional"
        else rules["consolidated_stale_days"]
        if effective_status == "consolidated"
        else rules["confirmed_stale_days"]
    )
    if age_days >= int(rules["retire_days"]):
        return "retired"
    if age_days >= stale_days:
        return "stale"
    return effective_status


def salience_for_memory_status(status: str) -> float:
    normalized = str(status or "provisional").strip() or "provisional"
    return {
        "confirmed": 1.0,
        "consolidated": 0.82,
        "provisional": 0.45,
        "stale": 0.18,
        "retired": 0.0,
        "rejected": 0.0,
    }.get(normalized, 0.35)


def _build_consolidated_item(
    view_key: str,
    events: list[dict[str, Any]],
    *,
    now: datetime | None = None,
) -> dict[str, Any]:
    latest_event = max(events, key=_chronological_key)
    representative = max(events, key=_representative_key)
    statuses = [str(event.get("status") or "").strip() for event in events]
    has_confirmed_support = any(status in RUNTIME_CONFIRMED_STATUSES for status in statuses)
    effective_status = classify_memory_status_decay(
        view_key,
        base_status=str(latest_event.get("status") or representative.get("status") or "provisional"),
        latest_created_at=str(latest_event.get("created_at") or ""),
        support_count=len(events),
        has_confirmed_support=has_confirmed_support,
        now=now,
    )

    title = str(
        representative.get("title")
        or latest_event.get("title")
        or representative.get("summary")
        or latest_event.get("summary")
        or view_key
    ).strip()
    summary = _best_non_empty(
        representative.get("summary"),
        latest_event.get("summary"),
    )
    content = _best_non_empty(
        representative.get("content"),
        latest_event.get("content"),
    )
    metadata = dict(representative.get("metadata") or {})
    if not metadata:
        metadata = dict(latest_event.get("metadata") or {})

    recent_summaries: list[str] = []
    for event in sorted(events, key=_chronological_key, reverse=True):
        candidate = str(event.get("summary") or "").strip()
        if candidate and candidate not in recent_summaries:
            recent_summaries.append(candidate)
        if len(recent_summaries) >= 3:
            break

    return {
        "item_key": _event_signature(view_key, representative),
        "title": title,
        "summary": summary,
        "content": content,
        "view_key": view_key,
        "effective_status": effective_status,
        "base_status": str(latest_event.get("status") or representative.get("status") or "provisional"),
        "trust_label": str(representative.get("trust_label") or latest_event.get("trust_label") or "unknown"),
        "salience": salience_for_memory_status(effective_status),
        "support_count": len(events),
        "supporting_event_ids": [
            str(event.get("event_id") or "")
            for event in sorted(events, key=_chronological_key, reverse=True)
        ],
        "latest_created_at": str(latest_event.get("created_at") or ""),
        "first_created_at": str(min(events, key=_chronological_key).get("created_at") or ""),
        "representative_event_id": representative.get("event_id"),
        "representative_event_type": representative.get("event_type"),
        "metadata": metadata,
        "recent_summaries": recent_summaries,
    }


def _find_group(
    groups: list[dict[str, Any]],
    *,
    signature: str,
    terms: set[str],
) -> dict[str, Any] | None:
    for group in groups:
        if group["signature"] == signature:
            return group

    if not terms:
        return None

    best_group: dict[str, Any] | None = None
    best_score = 0.0
    for group in groups:
        group_terms = set(group.get("terms") or set())
        if not group_terms:
            continue
        union = terms | group_terms
        if not union:
            continue
        score = len(terms & group_terms) / len(union)
        if score >= _SIMILARITY_THRESHOLD and score > best_score:
            best_group = group
            best_score = score
    return best_group


def _event_signature(view_key: str, event: dict[str, Any]) -> str:
    metadata = dict(event.get("metadata") or {})

    if view_key in HIGH_IMPACT_VIEW_KEYS:
        structured: dict[str, Any] = {
            key: metadata.get(key)
            for key in sorted(HIGH_IMPACT_METADATA_KEYS)
            if metadata.get(key) not in (None, "", [], {})
        }
        if structured:
            return f"structured:{json.dumps(structured, ensure_ascii=False, sort_keys=True)}"

    if view_key == "killed-ideas":
        for key in ("idea_id", "snapshot_id"):
            value = str(metadata.get(key) or "").strip()
            if value:
                return f"{key}:{value}"

    summary = str(event.get("summary") or "").strip().lower()
    content = str(event.get("content") or "").strip().lower()
    terms = sorted(_event_terms(event))
    if terms:
        return "text:" + "|".join(terms[:8])
    return f"text:{summary[:120]}|{content[:120]}"


def _event_terms(event: dict[str, Any]) -> set[str]:
    text = " ".join(
        [
            str(event.get("title") or ""),
            str(event.get("summary") or ""),
            str(event.get("content") or ""),
        ]
    ).lower()
    terms = {
        term
        for term in _TERM_RE.findall(text)
        if term not in _STOPWORDS and not term.isdigit()
    }
    return terms


def _chronological_key(event: dict[str, Any]) -> tuple[str, str]:
    return (
        str(event.get("created_at") or ""),
        str(event.get("event_id") or ""),
    )


def _representative_key(event: dict[str, Any]) -> tuple[int, int, str, str]:
    status = str(event.get("status") or "provisional").strip() or "provisional"
    trust = str(event.get("trust_label") or "unknown").strip()
    return (
        int(_STATUS_PRIORITY.get(status, -1)),
        int(_TRUST_PRIORITY.get(trust, 0)),
        str(event.get("created_at") or ""),
        str(event.get("event_id") or ""),
    )


def _best_non_empty(*candidates: Any) -> str:
    for candidate in candidates:
        text = str(candidate or "").strip()
        if text:
            return text
    return ""


def _age_in_days(created_at: str, *, now: datetime | None = None) -> int:
    timestamp = str(created_at or "").strip()
    if not timestamp:
        return 0
    try:
        created = datetime.fromisoformat(timestamp)
    except ValueError:
        return 0
    current = now or datetime.now(created.tzinfo)
    return max(int((current - created).total_seconds() // 86400), 0)
