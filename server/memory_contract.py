"""Typed contract helpers for advisory memory views.

This module locks the first-class memory view surface without widening the
runtime into capture orchestration or maintenance work. The contract answers:

- which typed views exist today
- which event types each view accepts
- which statuses each view allows
- how read ordering should treat ``assistant-brief``
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterable

from server.active_threads import validate_active_thread_event

MEMORY_VIEW_CONTRACT_VERSION = "2026-04-09"

_TYPED_MEMORY_EVENT_TYPES = frozenset(
    {
        "dialogue_capture",
        "preference_update",
        "profile_update",
        "thread_update",
        "idea_outcome",
        "contradiction_note",
    }
)

_TYPED_MEMORY_STATUSES = frozenset(
    {
        "provisional",
        "confirmed",
        "consolidated",
        "stale",
        "retired",
        "rejected",
    }
)


@dataclass(frozen=True)
class MemoryViewSpec:
    view_key: str
    title: str
    description: str
    read_role: str
    summary_only: bool
    allowed_event_types: frozenset[str]
    allowed_statuses: frozenset[str]


_TYPED_MEMORY_VIEWS: dict[str, MemoryViewSpec] = {
    "assistant-brief": MemoryViewSpec(
        view_key="assistant-brief",
        title="Assistant Brief",
        description=(
            "Short assistant-facing memory brief. Read this before pulling more "
            "specific memory views."
        ),
        read_role="entrypoint-summary",
        summary_only=True,
        allowed_event_types=_TYPED_MEMORY_EVENT_TYPES,
        allowed_statuses=frozenset({"provisional", "confirmed", "consolidated"}),
    ),
    "taste": MemoryViewSpec(
        view_key="taste",
        title="Taste",
        description=(
            "Compiled advisory memory view of the user's research taste, "
            "evaluation preferences, and recurring skepticism."
        ),
        read_role="specific-view",
        summary_only=False,
        allowed_event_types=frozenset({"dialogue_capture", "preference_update"}),
        allowed_statuses=frozenset(
            {"provisional", "confirmed", "consolidated", "stale", "retired"}
        ),
    ),
    "profile": MemoryViewSpec(
        view_key="profile",
        title="Profile",
        description=(
            "Compiled advisory memory view of the user's stable research "
            "direction, constraints, and long-lived context."
        ),
        read_role="specific-view",
        summary_only=False,
        allowed_event_types=frozenset({"dialogue_capture", "profile_update"}),
        allowed_statuses=frozenset(
            {"provisional", "confirmed", "consolidated", "stale", "retired"}
        ),
    ),
    "active-threads": MemoryViewSpec(
        view_key="active-threads",
        title="Active Threads",
        description=(
            "Compiled advisory memory view of the user's currently active "
            "research threads, workstreams, and open loops."
        ),
        read_role="specific-view",
        summary_only=False,
        allowed_event_types=frozenset({"dialogue_capture", "thread_update"}),
        allowed_statuses=frozenset(
            {"provisional", "confirmed", "consolidated", "stale", "retired"}
        ),
    ),
    "killed-ideas": MemoryViewSpec(
        view_key="killed-ideas",
        title="Killed Ideas",
        description=(
            "Compiled advisory memory view of rejected, contradicted, or "
            "deprioritized ideas worth avoiding or revisiting carefully."
        ),
        read_role="specific-view",
        summary_only=False,
        allowed_event_types=frozenset(
            {"dialogue_capture", "idea_outcome", "contradiction_note"}
        ),
        allowed_statuses=frozenset(
            {
                "provisional",
                "confirmed",
                "consolidated",
                "rejected",
                "stale",
                "retired",
            }
        ),
    ),
}


def typed_memory_view_keys() -> tuple[str, ...]:
    return tuple(_TYPED_MEMORY_VIEWS.keys())


def get_memory_view_spec(view_key: str) -> MemoryViewSpec | None:
    return _TYPED_MEMORY_VIEWS.get(view_key)


def order_memory_view_keys(view_keys: Iterable[str]) -> list[str]:
    seen: set[str] = set()
    ordered: list[str] = []
    others: list[str] = []
    has_assistant_brief = False

    for raw_key in view_keys:
        key = str(raw_key or "").strip()
        if not key or key in seen:
            continue
        seen.add(key)
        if key == "assistant-brief":
            has_assistant_brief = True
        else:
            others.append(key)

    if has_assistant_brief:
        ordered.append("assistant-brief")
    ordered.extend(others)
    return ordered


def validate_typed_memory_event(event: dict[str, Any]) -> None:
    typed_keys = [key for key in event.get("view_keys", []) if get_memory_view_spec(str(key))]
    if not typed_keys:
        return

    status = str(event.get("status") or "").strip()
    event_type = str(event.get("event_type") or "").strip()
    if status not in _TYPED_MEMORY_STATUSES:
        raise ValueError(
            "Typed memory event requires a supported status: "
            + ", ".join(sorted(_TYPED_MEMORY_STATUSES))
        )
    if event_type not in _TYPED_MEMORY_EVENT_TYPES:
        raise ValueError(
            "Typed memory event requires a supported event_type: "
            + ", ".join(sorted(_TYPED_MEMORY_EVENT_TYPES))
        )

    for view_key in typed_keys:
        spec = get_memory_view_spec(str(view_key))
        if spec is None:
            continue
        if event_type not in spec.allowed_event_types:
            raise ValueError(
                f"Memory event_type '{event_type}' is not allowed for view '{spec.view_key}'."
            )
        if status not in spec.allowed_statuses:
            raise ValueError(
                f"Memory status '{status}' is not allowed for view '{spec.view_key}'."
            )
        if spec.view_key == "active-threads":
            validate_active_thread_event(event)


def build_memory_view_frontmatter(
    view_key: str,
    *,
    compiled_at: str,
    compiled_event_count: int,
) -> dict[str, Any]:
    frontmatter: dict[str, Any] = {
        "view_key": view_key,
        "compiled_at": compiled_at,
        "compiled_event_count": compiled_event_count,
        "source": "memory-compile",
    }
    spec = get_memory_view_spec(view_key)
    if spec is None:
        return frontmatter

    frontmatter.update(
        {
            "view_type": "typed-memory-view",
            "contract_version": MEMORY_VIEW_CONTRACT_VERSION,
            "title": spec.title,
            "read_role": spec.read_role,
            "summary_only": spec.summary_only,
            "allowed_event_types": sorted(spec.allowed_event_types),
            "allowed_statuses": sorted(spec.allowed_statuses),
        }
    )
    return frontmatter


def public_memory_view_contract(view_key: str) -> dict[str, Any]:
    spec = get_memory_view_spec(view_key)
    if spec is None:
        return {"typed": False}

    return {
        "typed": True,
        "contract_version": MEMORY_VIEW_CONTRACT_VERSION,
        "title": spec.title,
        "description": spec.description,
        "read_role": spec.read_role,
        "summary_only": spec.summary_only,
        "allowed_event_types": sorted(spec.allowed_event_types),
        "allowed_statuses": sorted(spec.allowed_statuses),
    }
