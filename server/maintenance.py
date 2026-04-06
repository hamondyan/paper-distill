"""Maintenance Queue management.

Implements the three-layer design from review-2-v2:

    lint_vault() / vault_stats()        ← pure-read, no side effects
            │
            ▼ returns structured results
    reconcile_maintenance_queue()       ← explicit step, dedup + write
            │
            ▼
      maintenance_queue (SQLite)        ← authority layer
            │
            ▼ consumed at compile time
      execute merge / promote / refresh
            │
            ▼
      maintenance_queue (status=done)

Key invariant: lint functions remain pure-read.  Only
``reconcile_maintenance_queue()`` writes to the queue, and it deduplicates
against existing pending/confirmed tasks.
"""
from __future__ import annotations

import json
import logging
from typing import Any

from server.concept_registry import auto_merge_eligible, slugify
from server.database import get_db, _now_iso

LOG = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Reconcile: lint results → maintenance queue (deduped)
# ---------------------------------------------------------------------------

def reconcile_maintenance_queue(
    vault_path: str,
    lint_results: dict[str, Any] | None = None,
    stats_results: dict[str, Any] | None = None,
    auto_confirm: bool = True,
) -> dict[str, Any]:
    """Convert lint/stats findings into deduplicated maintenance tasks.

    Compares incoming findings against existing pending/confirmed tasks
    to avoid duplicates.  Optionally auto-confirms tasks that meet the
    hard-coded eligibility rules.

    Parameters
    ----------
    lint_results : dict
        Output of ``lint_vault_sync()``.
    stats_results : dict
        Output of ``vault_stats_sync()``.
    auto_confirm : bool
        If True, automatically confirm tasks that pass
        ``_auto_confirm_eligible()``.

    Returns
    -------
    dict with ``created``, ``skipped_duplicate``, ``auto_confirmed`` counts
    and the list of new task IDs.
    """
    conn = get_db(vault_path)
    now = _now_iso()
    created = 0
    skipped = 0
    auto_confirmed = 0
    new_ids: list[int] = []

    # Load existing active tasks for dedup
    active_payloads = _active_task_payloads(conn)

    # --- From lint: semantic_duplicates → merge_candidate tasks ---
    if lint_results:
        for dup in lint_results.get("semantic_duplicates", {}).get("items", []):
            payload = {
                "file_a": dup.get("file_a", ""),
                "title_a": dup.get("title_a", ""),
                "file_b": dup.get("file_b", ""),
                "title_b": dup.get("title_b", ""),
                "similarity": dup.get("similarity", 0),
            }
            dedup_key = _dedup_key("merge_candidate", payload)
            if dedup_key in active_payloads:
                skipped += 1
                continue

            confidence = dup.get("similarity", 0.0)
            task_id = _insert_task(
                conn, "merge_candidate", payload, confidence, now,
            )
            new_ids.append(task_id)
            created += 1

            # Auto-confirm if eligible
            if auto_confirm and _auto_confirm_eligible("merge_candidate", payload):
                _update_status(conn, task_id, "confirmed", now)
                auto_confirmed += 1

        # --- From lint: orphaned_articles → orphan_fix tasks ---
        for orphan in lint_results.get("orphaned_articles", {}).get("items", []):
            payload = {"file": orphan}
            dedup_key = _dedup_key("orphan_fix", payload)
            if dedup_key in active_payloads:
                skipped += 1
                continue
            task_id = _insert_task(conn, "orphan_fix", payload, 0.5, now)
            new_ids.append(task_id)
            created += 1

        # --- From lint: missing_concept_stubs → concept stubs ---
        for concept_key in lint_results.get("missing_concept_stubs", {}).get("items", []):
            payload = {"concept_key": concept_key}
            dedup_key = _dedup_key("missing_concept_stub", payload)
            if dedup_key in active_payloads:
                skipped += 1
                continue
            task_id = _insert_task(conn, "missing_concept_stub", payload, 0.7, now)
            new_ids.append(task_id)
            created += 1

    # --- From stats: promotion_candidates → promote_to_topic tasks ---
    if stats_results:
        for candidate in stats_results.get("promotion_candidates", []):
            concept_name = candidate.get("concept", "")
            payload = {
                "concept": concept_name,
                "paper_count": candidate.get("paper_count", 0),
            }
            dedup_key = _dedup_key("promote_to_topic", payload)
            if dedup_key in active_payloads:
                skipped += 1
                continue
            task_id = _insert_task(
                conn, "promote_to_topic", payload,
                min(candidate.get("paper_count", 0) / 10.0, 1.0), now,
            )
            new_ids.append(task_id)
            created += 1

        # --- From stats: stale_topics → stale_topic_refresh tasks ---
        for stale in stats_results.get("stale_topics", []):
            payload = {
                "topic": stale.get("topic", ""),
                "new_paper_count": stale.get("new_paper_count", 0),
                "reasons": stale.get("reasons", []),
            }
            dedup_key = _dedup_key("stale_topic_refresh", payload)
            if dedup_key in active_payloads:
                skipped += 1
                continue
            task_id = _insert_task(
                conn, "stale_topic_refresh", payload, 0.6, now,
            )
            new_ids.append(task_id)
            created += 1

    conn.commit()
    return {
        "created": created,
        "skipped_duplicate": skipped,
        "auto_confirmed": auto_confirmed,
        "new_task_ids": new_ids,
    }


# ---------------------------------------------------------------------------
# Task CRUD
# ---------------------------------------------------------------------------

def get_pending_tasks(
    vault_path: str,
    task_type: str | None = None,
    status: str | None = None,
) -> list[dict[str, Any]]:
    """List maintenance tasks, optionally filtered by type and status."""
    conn = get_db(vault_path)
    query = "SELECT * FROM maintenance_queue WHERE 1=1"
    params: list[Any] = []

    if task_type:
        query += " AND task_type = ?"
        params.append(task_type)
    if status:
        query += " AND status = ?"
        params.append(status)
    else:
        # Default: show non-terminal statuses
        query += " AND status IN ('pending', 'confirmed', 'processing')"

    query += " ORDER BY created_at DESC"
    rows = conn.execute(query, params).fetchall()
    result = []
    for row in rows:
        d = dict(row)
        try:
            d["payload"] = json.loads(d["payload"])
        except (json.JSONDecodeError, TypeError):
            pass
        result.append(d)
    return result


def confirm_task(vault_path: str, task_id: int) -> dict[str, Any]:
    """Mark a task as confirmed (ready for execution)."""
    conn = get_db(vault_path)
    row = conn.execute(
        "SELECT * FROM maintenance_queue WHERE id = ?", (task_id,)
    ).fetchone()
    if not row:
        return {"error": f"Task {task_id} not found"}
    if row["status"] not in ("pending",):
        return {"error": f"Task {task_id} is '{row['status']}', cannot confirm"}

    _update_status(conn, task_id, "confirmed", _now_iso())
    conn.commit()
    return {"confirmed": True, "task_id": task_id}


def reject_task(vault_path: str, task_id: int, reason: str = "") -> dict[str, Any]:
    """Mark a task as rejected."""
    conn = get_db(vault_path)
    row = conn.execute(
        "SELECT * FROM maintenance_queue WHERE id = ?", (task_id,)
    ).fetchone()
    if not row:
        return {"error": f"Task {task_id} not found"}
    if row["status"] in ("done", "rejected"):
        return {"error": f"Task {task_id} is already '{row['status']}'"}

    _update_status(conn, task_id, "rejected", _now_iso())
    conn.commit()
    return {"rejected": True, "task_id": task_id}


def complete_task(vault_path: str, task_id: int) -> dict[str, Any]:
    """Mark a task as done after execution."""
    conn = get_db(vault_path)
    row = conn.execute(
        "SELECT * FROM maintenance_queue WHERE id = ?", (task_id,)
    ).fetchone()
    if not row:
        return {"error": f"Task {task_id} not found"}

    _update_status(conn, task_id, "done", _now_iso())
    conn.commit()
    return {"completed": True, "task_id": task_id}


# ---------------------------------------------------------------------------
# Auto-confirm eligibility
# ---------------------------------------------------------------------------

def _auto_confirm_eligible(task_type: str, payload: dict) -> bool:
    """Determine if a task can be auto-confirmed.

    Only three cases qualify (matching the concept registry auto-merge rules):
    1. Slug-identical concepts
    2. Abbreviation ↔ full name in the hard-coded whitelist
    3. Spelling variants

    All other tasks require human confirmation.
    """
    if task_type != "merge_candidate":
        return False

    title_a = payload.get("title_a", "")
    title_b = payload.get("title_b", "")
    if not title_a or not title_b:
        return False

    reason = auto_merge_eligible(title_a, title_b)
    return reason is not None


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _insert_task(
    conn, task_type: str, payload: dict, confidence: float, now: str,
) -> int:
    """Insert a task and return its ID."""
    cursor = conn.execute(
        """INSERT INTO maintenance_queue
           (task_type, payload, confidence, status, created_at)
           VALUES (?, ?, ?, 'pending', ?)""",
        (task_type, json.dumps(payload, ensure_ascii=False), confidence, now),
    )
    return cursor.lastrowid


def _update_status(conn, task_id: int, status: str, now: str) -> None:
    """Update task status and resolved_at timestamp."""
    conn.execute(
        """UPDATE maintenance_queue
           SET status = ?, resolved_at = ?
           WHERE id = ?""",
        (status, now, task_id),
    )


def _active_task_payloads(conn) -> set[str]:
    """Return dedup keys for all non-terminal tasks."""
    rows = conn.execute(
        """SELECT task_type, payload FROM maintenance_queue
           WHERE status IN ('pending', 'confirmed', 'processing')"""
    ).fetchall()
    keys: set[str] = set()
    for row in rows:
        try:
            payload = json.loads(row["payload"])
        except (json.JSONDecodeError, TypeError):
            payload = {}
        keys.add(_dedup_key(row["task_type"], payload))
    return keys


def _dedup_key(task_type: str, payload: dict) -> str:
    """Generate a stable dedup key from task type and payload essentials.

    Uses only the identity-determining fields, not mutable metadata like
    similarity scores or timestamps.
    """
    if task_type == "merge_candidate":
        pair = sorted([payload.get("file_a", ""), payload.get("file_b", "")])
        return f"merge:{pair[0]}|{pair[1]}"
    if task_type == "promote_to_topic":
        return f"promote:{payload.get('concept', '')}"
    if task_type == "stale_topic_refresh":
        return f"refresh:{payload.get('topic', '')}"
    if task_type == "orphan_fix":
        return f"orphan:{payload.get('file', '')}"
    if task_type == "missing_concept_stub":
        return f"stub:{payload.get('concept_key', '')}"
    # Fallback
    return f"{task_type}:{json.dumps(payload, sort_keys=True)}"
