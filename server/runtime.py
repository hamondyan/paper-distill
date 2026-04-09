"""Single-writer runtime for durable mutations.

Wave 1 keeps the executor in-process, but every durable mutation still enters
through a SQLite-backed queue so crashes leave recoverable runtime truth.
"""
from __future__ import annotations

import hashlib
import json
import logging
import os
import threading
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Callable

from server.database import _now_iso, get_db

LOG = logging.getLogger(__name__)

_ACTIVE_STATUSES = ("pending", "processing")
_PROCESSING_STALE_AFTER_SECONDS = 30

_executor_locks_guard = threading.Lock()
_executor_locks: dict[str, threading.Lock] = {}
_mutation_handlers: dict[str, Callable[[str, dict[str, Any]], dict[str, Any]]] = {}


def register_mutation_handler(
    mutation_type: str,
    handler: Callable[[str, dict[str, Any]], dict[str, Any]],
) -> None:
    """Register a handler for a durable mutation type."""
    _mutation_handlers[mutation_type] = handler


def enqueue_mutation(
    vault_path: str,
    *,
    mutation_type: str,
    target_key: str,
    payload: dict[str, Any],
) -> dict[str, Any]:
    """Persist a mutation request, deduping only identical active rows."""
    conn = get_db(vault_path)
    now = _now_iso()
    payload_json = json.dumps(payload, ensure_ascii=False, sort_keys=True)
    payload_hash = hashlib.sha256(payload_json.encode("utf-8")).hexdigest()[:16]

    existing = conn.execute(
        """
        SELECT id, status
        FROM mutation_queue
        WHERE mutation_type = ?
          AND target_key = ?
          AND payload_hash = ?
          AND status IN ('pending', 'processing')
        ORDER BY id ASC
        LIMIT 1
        """,
        (mutation_type, target_key, payload_hash),
    ).fetchone()
    if existing:
        return {
            "created": False,
            "duplicate": True,
            "mutation_id": existing["id"],
            "status": existing["status"],
        }

    cur = conn.execute(
        """
        INSERT INTO mutation_queue
            (mutation_type, target_key, payload_json, payload_hash, status,
             created_at, updated_at)
        VALUES (?, ?, ?, ?, 'pending', ?, ?)
        """,
        (mutation_type, target_key, payload_json, payload_hash, now, now),
    )
    conn.commit()
    return {
        "created": True,
        "duplicate": False,
        "mutation_id": cur.lastrowid,
        "status": "pending",
    }


def submit_mutation(
    vault_path: str,
    *,
    mutation_type: str,
    target_key: str,
    payload: dict[str, Any],
) -> dict[str, Any]:
    """Enqueue then opportunistically drain until the mutation reaches terminal state."""
    enqueued = enqueue_mutation(
        vault_path,
        mutation_type=mutation_type,
        target_key=target_key,
        payload=payload,
    )
    drain_mutation_queue(vault_path)
    record = get_mutation_record(vault_path, enqueued["mutation_id"])
    result = dict(record.get("result") or {})
    result.setdefault("mutation_id", enqueued["mutation_id"])
    if record.get("status") == "failed" and "error" not in result:
        result["error"] = record.get("error") or f"{mutation_type} failed"
    return result


def drain_mutation_queue(vault_path: str, max_items: int | None = None) -> dict[str, Any]:
    """Drain queued mutations under a per-vault process lock."""
    lock = _executor_lock(vault_path)
    executor_id = f"{os.getpid()}:{threading.get_ident()}"
    processed = 0

    with lock:
        conn = get_db(vault_path)
        _reset_stale_processing(conn)
        while True:
            row = _claim_next_mutation(conn, executor_id)
            if not row:
                break
            try:
                result = _dispatch_mutation(vault_path, row)
            except Exception as exc:
                LOG.exception("Mutation %s failed", row["id"])
                _finish_mutation(
                    conn,
                    row["id"],
                    status="failed",
                    result={"error": str(exc)},
                    error=str(exc),
                )
            processed += 1
            if max_items is not None and processed >= max_items:
                break
    return {"processed": processed}


def get_mutation_record(vault_path: str, mutation_id: int) -> dict[str, Any]:
    """Return a decoded mutation row."""
    conn = get_db(vault_path)
    row = conn.execute(
        "SELECT * FROM mutation_queue WHERE id = ?",
        (mutation_id,),
    ).fetchone()
    if not row:
        return {}
    decoded = dict(row)
    decoded["payload"] = _decode_json(decoded.get("payload_json"))
    decoded["result"] = _decode_json(decoded.get("result_json"))
    return decoded


def _executor_lock(vault_path: str) -> threading.Lock:
    key = str(Path(vault_path).expanduser().resolve())
    with _executor_locks_guard:
        lock = _executor_locks.get(key)
        if lock is None:
            lock = threading.Lock()
            _executor_locks[key] = lock
        return lock


def _reset_stale_processing(conn: Any) -> None:
    cutoff = datetime.now() - timedelta(seconds=_PROCESSING_STALE_AFTER_SECONDS)
    rows = conn.execute(
        "SELECT id, claimed_at FROM mutation_queue WHERE status = 'processing'"
    ).fetchall()
    for row in rows:
        claimed_at = row["claimed_at"]
        try:
            claimed_dt = datetime.fromisoformat(claimed_at) if claimed_at else None
        except ValueError:
            claimed_dt = None
        if claimed_dt is None or claimed_dt <= cutoff:
            now = _now_iso()
            conn.execute(
                """
                UPDATE mutation_queue
                SET status = 'pending',
                    claimed_by = NULL,
                    claimed_at = NULL,
                    updated_at = ?
                WHERE id = ?
                """,
                (now, row["id"]),
            )
    conn.commit()


def _claim_next_mutation(conn: Any, executor_id: str) -> dict[str, Any] | None:
    while True:
        conn.execute("BEGIN IMMEDIATE")
        row = conn.execute(
            """
            SELECT *
            FROM mutation_queue
            WHERE status = 'pending'
            ORDER BY id ASC
            LIMIT 1
            """
        ).fetchone()
        if not row:
            conn.commit()
            return None

        now = _now_iso()
        cur = conn.execute(
            """
            UPDATE mutation_queue
            SET status = 'processing',
                claimed_by = ?,
                claimed_at = ?,
                attempts = attempts + 1,
                updated_at = ?
            WHERE id = ? AND status = 'pending'
            """,
            (executor_id, now, now, row["id"]),
        )
        conn.commit()
        if cur.rowcount == 1:
            claimed = conn.execute(
                "SELECT * FROM mutation_queue WHERE id = ?",
                (row["id"],),
            ).fetchone()
            return dict(claimed) if claimed else None


def _dispatch_mutation(vault_path: str, row: dict[str, Any]) -> dict[str, Any]:
    mutation_type = row["mutation_type"]
    handler = _mutation_handlers.get(mutation_type)
    if handler is None and mutation_type == "compile_publish":
        from server.compile_ir import execute_compile_publish_mutation

        handler = execute_compile_publish_mutation
        register_mutation_handler(mutation_type, handler)
    if handler is None and mutation_type == "memory_append":
        from server.memory_runtime import execute_memory_append_mutation

        handler = execute_memory_append_mutation
        register_mutation_handler(mutation_type, handler)
    if handler is None and mutation_type == "idea_verify":
        from server.idea_verification import execute_idea_verify_mutation

        handler = execute_idea_verify_mutation
        register_mutation_handler(mutation_type, handler)
    if handler is None:
        raise ValueError(f"Unknown mutation_type: {mutation_type}")

    result = handler(vault_path, row)
    status = "failed" if result.get("error") else "done"
    _finish_mutation(
        get_db(vault_path),
        row["id"],
        status=status,
        result=result,
        error=result.get("error"),
    )
    return result


def _finish_mutation(
    conn: Any,
    mutation_id: int,
    *,
    status: str,
    result: dict[str, Any] | None = None,
    error: str | None = None,
) -> None:
    now = _now_iso()
    conn.execute(
        """
        UPDATE mutation_queue
        SET status = ?,
            result_json = ?,
            error = ?,
            updated_at = ?
        WHERE id = ?
        """,
        (
            status,
            json.dumps(result or {}, ensure_ascii=False, sort_keys=True),
            error,
            now,
            mutation_id,
        ),
    )
    conn.commit()


def _decode_json(raw: Any) -> dict[str, Any]:
    if not raw:
        return {}
    try:
        data = json.loads(raw)
    except (TypeError, json.JSONDecodeError):
        return {}
    return data if isinstance(data, dict) else {}
