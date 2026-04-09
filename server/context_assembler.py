"""Task-aware runtime context assembly for discovery, query, and ideation.

This module centralizes the "small but high-signal" context packet that the
runtime can assemble from two local sources:

- settings.json -> research_profile
- Paper Distill/memory -> typed advisory memory views and fresh overlay events

The goal is not to recreate a giant orchestrator. It is to give discovery,
query, and idea-generation paths one narrow place to ask:
"what should the assistant remember about the user's taste and profile right
now?"
"""
from __future__ import annotations

import re
from collections import Counter
from pathlib import Path
from typing import Any

from server.config import get_paper_distill_settings
from server.memory_consolidation import (
    runtime_effective_memory_items,
)
from server.memory_promotion import HIGH_IMPACT_VIEW_KEYS
from server.memory_runtime import list_memory_events, read_memory_views
from server.vault_contract import paper_distill_root

_DEFAULT_VIEW_KEYS = ("assistant-brief", "profile", "taste")
_TERM_RE = re.compile(r"[a-z0-9][a-z0-9-]{2,}")
_MAX_SIGNAL_TEXT = 900
_MAX_SIGNAL_SUMMARY = 280
_MAX_EVIDENCE_ITEMS = 6
_STOPWORDS = {
    "about",
    "after",
    "again",
    "also",
    "analysis",
    "assistant",
    "because",
    "before",
    "being",
    "between",
    "brief",
    "build",
    "compiled",
    "current",
    "does",
    "explicit",
    "from",
    "have",
    "into",
    "just",
    "keep",
    "more",
    "most",
    "needs",
    "over",
    "paper",
    "papers",
    "profile",
    "query",
    "read",
    "runtime",
    "should",
    "signal",
    "signals",
    "summary",
    "taste",
    "that",
    "their",
    "then",
    "they",
    "this",
    "user",
    "using",
    "view",
    "views",
    "with",
}


def assemble_runtime_context(
    vault_path: str | None,
    *,
    task: str,
    query_text: str | None = None,
    topic_keys: list[str] | None = None,
    user_topics: list[str] | None = None,
) -> dict[str, Any]:
    """Return a compact runtime context packet for one task."""
    settings = get_paper_distill_settings()
    research_profile = _research_profile_packet(settings)
    requested_view_keys = list(_DEFAULT_VIEW_KEYS)

    memory_state = _safe_read_memory_state(vault_path, requested_view_keys)
    memory_events = _safe_list_memory_events(vault_path, requested_view_keys)
    events_by_view = _events_by_view(memory_events)
    effective_items_by_view = {
        view_key: runtime_effective_memory_items(view_key, list(events_by_view.get(view_key, [])))
        for view_key in requested_view_keys
    }

    views: dict[str, Any] = {}
    for view_key in requested_view_keys:
        views[view_key] = _build_view_packet(
            vault_path,
            view_key=view_key,
            state_view=dict(memory_state.get("views", {}).get(view_key) or {}),
            events=list(events_by_view.get(view_key, [])),
            effective_items=list(effective_items_by_view.get(view_key, [])),
        )

    structured_overrides = _structured_overrides(effective_items_by_view)
    effective_preferences = _effective_preferences(
        research_profile=research_profile,
        structured_overrides=structured_overrides,
        views=views,
        query_text=query_text,
        topic_keys=topic_keys,
        user_topics=user_topics,
    )

    return {
        "task": task,
        "query_text": str(query_text or "").strip(),
        "topic_keys": _normalize_string_list(topic_keys),
        "user_topics": _normalize_string_list(user_topics),
        "trust_order": ["settings", "assistant-brief", "profile", "taste"],
        "requested_view_keys": requested_view_keys,
        "research_profile": research_profile,
        "memory": {
            "available": any(view["available"] for view in views.values()),
            "overlay_applied": bool(memory_state.get("overlay_applied")),
            "uncompiled_event_count": int(memory_state.get("uncompiled_event_count") or 0),
            "views": views,
            "local_evidence": _local_memory_evidence(views),
        },
        "effective_preferences": effective_preferences,
    }


def _research_profile_packet(settings: dict[str, Any]) -> dict[str, Any]:
    profile = settings.get("research_profile", {})
    if not isinstance(profile, dict):
        profile = {}
    learned = profile.get("learned_preferences", {})
    if not isinstance(learned, dict):
        learned = {}

    return {
        "direction": str(profile.get("direction") or "").strip(),
        "whitelist_authors": _normalize_string_list(profile.get("whitelist_authors")),
        "seed_papers": _normalize_string_list(profile.get("seed_papers")),
        "learned_preferences": {
            "accepted_keywords": _normalize_string_list(learned.get("accepted_keywords")),
            "rejected_keywords": _normalize_string_list(learned.get("rejected_keywords")),
            "preferred_venues": _normalize_string_list(learned.get("preferred_venues")),
            "feedback_count": int(learned.get("feedback_count") or 0),
        },
    }


def _safe_read_memory_state(vault_path: str | None, view_keys: list[str]) -> dict[str, Any]:
    if not vault_path:
        return {"overlay_applied": False, "uncompiled_event_count": 0, "views": {}}
    try:
        return read_memory_views(vault_path, view_keys=view_keys)
    except Exception:
        return {"overlay_applied": False, "uncompiled_event_count": 0, "views": {}}


def _safe_list_memory_events(vault_path: str | None, view_keys: list[str]) -> list[dict[str, Any]]:
    if not vault_path:
        return []
    try:
        return list_memory_events(vault_path, view_keys=view_keys, limit=24)
    except Exception:
        return []


def _events_by_view(events: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    grouped: dict[str, list[dict[str, Any]]] = {}
    for event in events:
        for raw_key in event.get("view_keys") or []:
            key = str(raw_key or "").strip()
            if not key:
                continue
            grouped.setdefault(key, []).append(event)
    return grouped


def _build_view_packet(
    vault_path: str | None,
    *,
    view_key: str,
    state_view: dict[str, Any],
    events: list[dict[str, Any]],
    effective_items: list[dict[str, Any]],
) -> dict[str, Any]:
    overlay_events = list(state_view.get("overlay_events") or [])
    compiled_path = _paper_distill_path(vault_path, state_view.get("path"))
    fallback_path = _fallback_memory_view_path(view_key)
    signal_text = _view_signal_text(
        view_key=view_key,
        body=str(state_view.get("body") or "").strip(),
        overlay_events=overlay_events,
        effective_items=effective_items,
    )

    return {
        "view_key": view_key,
        "title": str(state_view.get("frontmatter", {}).get("title") or view_key).strip(),
        "available": bool(state_view.get("compiled") or overlay_events or signal_text),
        "compiled": bool(state_view.get("compiled")),
        "path": compiled_path or fallback_path,
        "overlay_count": len(overlay_events),
        "signal_summary": _truncate(signal_text, _MAX_SIGNAL_SUMMARY),
        "signal_text": signal_text,
        "keywords": _extract_terms(
            signal_text,
            *(str(item.get("summary") or "") for item in effective_items[:6]),
        ),
        "overlay_events": [
            {
                "event_id": event.get("event_id"),
                "title": event.get("title"),
                "summary": event.get("summary"),
                "excerpt": _truncate(str(event.get("content") or "").strip(), 220),
                "trust_label": event.get("trust_label"),
                "status": event.get("status"),
            }
            for event in overlay_events[:4]
        ],
    }


def _signal_text(*, body: str, overlay_events: list[dict[str, Any]]) -> str:
    parts: list[str] = []
    if body:
        parts.append(body)
    for event in overlay_events[:4]:
        summary = str(event.get("summary") or "").strip()
        content = str(event.get("content") or "").strip()
        if summary:
            parts.append(summary)
        if content:
            parts.append(content)
    return _truncate(_collapse_text(" ".join(parts)), _MAX_SIGNAL_TEXT)


def _view_signal_text(
    *,
    view_key: str,
    body: str,
    overlay_events: list[dict[str, Any]],
    effective_items: list[dict[str, Any]],
) -> str:
    if view_key not in HIGH_IMPACT_VIEW_KEYS:
        return _signal_text(body=body, overlay_events=overlay_events)

    parts: list[str] = []
    for item in effective_items[:6]:
        summary = str(item.get("summary") or "").strip()
        content = str(item.get("content") or "").strip()
        if summary:
            parts.append(summary)
        if content:
            parts.append(content)
    return _truncate(_collapse_text(" ".join(parts)), _MAX_SIGNAL_TEXT)


def _structured_overrides(items_by_view: dict[str, list[dict[str, Any]]]) -> dict[str, Any]:
    overrides = {
        "accepted_keywords": set(),
        "rejected_keywords": set(),
        "preferred_venues": set(),
        "whitelist_authors": set(),
        "seed_papers": set(),
        "direction_notes": [],
    }
    for items in items_by_view.values():
        for item in items:
            metadata = dict(item.get("metadata") or {})
            overrides["accepted_keywords"].update(
                _normalize_string_list(metadata.get("accepted_keywords"))
            )
            overrides["rejected_keywords"].update(
                _normalize_string_list(metadata.get("rejected_keywords"))
            )
            overrides["preferred_venues"].update(
                _normalize_string_list(metadata.get("preferred_venues"))
            )
            overrides["whitelist_authors"].update(
                _normalize_string_list(metadata.get("whitelist_authors"))
            )
            overrides["seed_papers"].update(
                _normalize_string_list(metadata.get("seed_papers"))
            )
            for candidate in (
                metadata.get("direction"),
                metadata.get("profile_direction"),
                metadata.get("research_direction"),
            ):
                note = str(candidate or "").strip()
                if note:
                    overrides["direction_notes"].append(note)
    return overrides


def _effective_preferences(
    *,
    research_profile: dict[str, Any],
    structured_overrides: dict[str, Any],
    views: dict[str, Any],
    query_text: str | None,
    topic_keys: list[str] | None,
    user_topics: list[str] | None,
) -> dict[str, Any]:
    learned = dict(research_profile.get("learned_preferences") or {})
    direction = str(research_profile.get("direction") or "").strip()
    direction_notes = [note for note in structured_overrides.get("direction_notes", []) if note]
    combined_direction = direction
    if direction_notes:
        combined_direction = ". ".join([part for part in [direction, *direction_notes] if part]).strip()

    accepted_keywords = _merge_unique_strings(
        learned.get("accepted_keywords"),
        sorted(structured_overrides.get("accepted_keywords") or set()),
    )
    rejected_keywords = _merge_unique_strings(
        learned.get("rejected_keywords"),
        sorted(structured_overrides.get("rejected_keywords") or set()),
    )
    preferred_venues = _merge_unique_strings(
        learned.get("preferred_venues"),
        sorted(structured_overrides.get("preferred_venues") or set()),
    )
    whitelist_authors = _merge_unique_strings(
        research_profile.get("whitelist_authors"),
        sorted(structured_overrides.get("whitelist_authors") or set()),
    )
    seed_papers = _merge_unique_strings(
        research_profile.get("seed_papers"),
        sorted(structured_overrides.get("seed_papers") or set()),
    )

    profile_signal = " ".join(
        [
            combined_direction,
            str(views.get("profile", {}).get("signal_text") or ""),
        ]
    ).strip()
    taste_signal = " ".join(
        [
            str(views.get("taste", {}).get("signal_text") or ""),
            str(views.get("assistant-brief", {}).get("signal_text") or ""),
        ]
    ).strip()

    profile_terms = _merge_unique_strings(
        accepted_keywords,
        _extract_terms(
            combined_direction,
            profile_signal,
            " ".join(_normalize_string_list(topic_keys)),
            " ".join(_normalize_string_list(user_topics)),
        ),
    )
    taste_terms = _extract_terms(
        taste_signal,
        " ".join(accepted_keywords),
        str(query_text or ""),
    )

    return {
        "direction": combined_direction,
        "whitelist_authors": whitelist_authors,
        "seed_papers": seed_papers,
        "accepted_keywords": accepted_keywords,
        "rejected_keywords": rejected_keywords,
        "preferred_venues": preferred_venues,
        "profile_terms": profile_terms,
        "taste_terms": taste_terms,
    }


def _local_memory_evidence(views: dict[str, Any]) -> list[dict[str, Any]]:
    evidence: list[dict[str, Any]] = []
    for view_key in ("profile", "taste"):
        view = dict(views.get(view_key) or {})
        ref = str(view.get("path") or _fallback_memory_view_path(view_key))
        signal_summary = str(view.get("signal_summary") or "").strip()
        if signal_summary:
            evidence.append(
                {
                    "ref": ref,
                    "view_key": view_key,
                    "summary": signal_summary,
                    "source_kind": "memory_view",
                }
            )
        for event in view.get("overlay_events") or []:
            summary = str(event.get("summary") or "").strip()
            if not summary:
                continue
            evidence.append(
                {
                    "ref": ref,
                    "view_key": view_key,
                    "summary": summary,
                    "title": str(event.get("title") or "").strip(),
                    "excerpt": str(event.get("excerpt") or "").strip(),
                    "trust_label": str(event.get("trust_label") or "").strip(),
                    "status": str(event.get("status") or "").strip(),
                    "source_kind": "memory_event",
                }
            )
        if len(evidence) >= _MAX_EVIDENCE_ITEMS:
            break
    return evidence[:_MAX_EVIDENCE_ITEMS]


def _extract_terms(*texts: str, limit: int = 14) -> list[str]:
    counts: Counter[str] = Counter()
    for text in texts:
        lowered = str(text or "").lower()
        for match in _TERM_RE.findall(lowered):
            if match in _STOPWORDS or match.isdigit():
                continue
            counts[match] += 1
    return [term for term, _ in counts.most_common(limit)]


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
        if not item:
            continue
        lower = item.lower()
        if lower in seen:
            continue
        seen.add(lower)
        normalized.append(item)
    return normalized


def _merge_unique_strings(*groups: Any) -> list[str]:
    merged: list[str] = []
    seen: set[str] = set()
    for group in groups:
        for item in _normalize_string_list(group):
            lowered = item.lower()
            if lowered in seen:
                continue
            seen.add(lowered)
            merged.append(item)
    return merged


def _collapse_text(text: str) -> str:
    return " ".join(str(text or "").split()).strip()


def _truncate(text: str, limit: int) -> str:
    normalized = str(text or "").strip()
    if len(normalized) <= limit:
        return normalized
    return normalized[: limit - 3].rstrip() + "..."


def _paper_distill_path(vault_path: str | None, raw_path: Any) -> str | None:
    path_text = str(raw_path or "").strip()
    if not path_text:
        return None
    if not vault_path:
        return path_text
    root = paper_distill_root(vault_path)
    try:
        relative = Path(path_text).expanduser().resolve().relative_to(root.resolve())
    except Exception:
        return path_text
    return f"Paper Distill/{relative.as_posix()}"


def _fallback_memory_view_path(view_key: str) -> str:
    return f"Paper Distill/memory/{view_key}.md"
