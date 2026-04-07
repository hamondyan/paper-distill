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
import os
import re
from typing import Any

import yaml

from server.concept_registry import auto_merge_eligible, get_concept, merge_concepts, promote_concept, slugify
from server.compile_ir import commit_compile_result
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

    # --- From lint: semantic paper duplicates → review tasks ---
    if lint_results:
        for dup in lint_results.get("semantic_duplicates", {}).get("items", []):
            payload = {
                "file_a": dup.get("file_a", ""),
                "title_a": dup.get("title_a", ""),
                "file_b": dup.get("file_b", ""),
                "title_b": dup.get("title_b", ""),
                "similarity": dup.get("similarity", 0),
            }
            dedup_key = _dedup_key("paper_duplicate_review", payload)
            if dedup_key in active_payloads:
                skipped += 1
                continue

            confidence = dup.get("similarity", 0.0)
            task_id = _insert_task(
                conn, "paper_duplicate_review", payload, confidence, now,
            )
            new_ids.append(task_id)
            created += 1

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
        query += " AND status IN ('pending', 'confirmed', 'processing', 'blocked')"

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


def enqueue_task(
    vault_path: str,
    task_type: str,
    payload: dict[str, Any],
    *,
    confidence: float = 1.0,
    status: str = "pending",
    auto_confirm: bool = False,
) -> dict[str, Any]:
    """Create a maintenance task explicitly, with deduplication.

    This is the manual/adjudicated path for concept merges, promotions, and
    refreshes. Unlike `reconcile_maintenance_queue`, it does not infer tasks
    from lint/stats; the caller supplies the exact payload.
    """
    conn = get_db(vault_path)
    dedup_key = _dedup_key(task_type, payload)
    if dedup_key in _active_task_payloads(conn):
        return {"created": False, "duplicate": True, "task_type": task_type}

    now = _now_iso()
    task_id = _insert_task(conn, task_type, payload, confidence, now)
    final_status = status
    if auto_confirm and _auto_confirm_eligible(task_type, payload):
        final_status = "confirmed"
    if final_status != "pending":
        _update_status(conn, task_id, final_status, now)
    conn.commit()
    return {
        "created": True,
        "task_id": task_id,
        "task_type": task_type,
        "status": final_status,
    }


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


def block_task(vault_path: str, task_id: int, reason: str = "") -> dict[str, Any]:
    """Mark a task as blocked by a conflict or unmet prerequisite."""
    conn = get_db(vault_path)
    row = conn.execute(
        "SELECT * FROM maintenance_queue WHERE id = ?", (task_id,)
    ).fetchone()
    if not row:
        return {"error": f"Task {task_id} not found"}
    _update_status(conn, task_id, "blocked", _now_iso())
    conn.commit()
    return {"blocked": True, "task_id": task_id, "reason": reason}


def fail_task(vault_path: str, task_id: int, reason: str = "") -> dict[str, Any]:
    """Mark a task as failed during execution."""
    conn = get_db(vault_path)
    row = conn.execute(
        "SELECT * FROM maintenance_queue WHERE id = ?", (task_id,)
    ).fetchone()
    if not row:
        return {"error": f"Task {task_id} not found"}
    _update_status(conn, task_id, "failed", _now_iso())
    conn.commit()
    return {"failed": True, "task_id": task_id, "reason": reason}


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
# Phase 3 execution controllers
# ---------------------------------------------------------------------------

def execute_merge(vault_path: str, task_id: int) -> dict[str, Any]:
    """Execute a confirmed merge task.

    Expected payload:
      {"from_id": "...", "to_id": "...", "reason": "..."}
    """
    task = _load_task(vault_path, task_id)
    if "error" in task:
        return task
    if task["status"] == "done":
        return {"already_applied": True, "task_id": task_id, "completed": True}
    if task["status"] not in {"confirmed", "processing"}:
        return {"error": f"Task {task_id} must be confirmed before execution"}

    payload = task["payload"]
    from_id = payload.get("from_id", "")
    to_id = payload.get("to_id", "")
    reason = payload.get("reason", "")
    if not from_id or not to_id:
        return block_task(vault_path, task_id, "merge task missing from_id/to_id")

    conn = get_db(vault_path)
    conn.execute(
        "UPDATE maintenance_queue SET status = 'processing' WHERE id = ?",
        (task_id,),
    )
    conn.commit()

    # Idempotent fast-path: already merged and target still exists.
    if get_concept(vault_path, from_id) is None and get_concept(vault_path, to_id) is not None:
        complete_task(vault_path, task_id)
        return {"already_applied": True, "task_id": task_id, "completed": True}

    result = merge_concepts(vault_path, from_id, to_id, reason)
    if "error" in result:
        return fail_task(vault_path, task_id, result["error"])

    # Re-point compile_deps to the merged target and current target version.
    target = get_concept(vault_path, to_id)
    dep_version = target["version"] if target else 1
    conn.execute(
        """UPDATE compile_deps
           SET dep_id = ?, dep_version = ?
           WHERE dep_id = ?""",
        (to_id, dep_version, from_id),
    )
    conn.commit()

    impacted_pages = _dependent_pages_for_ids(conn, [from_id, to_id])
    for page in impacted_pages:
        _rewrite_page_links(vault_path, page["page_id"], page["page_type"], from_id, to_id)
    complete_task(vault_path, task_id)
    return {
        **result,
        "completed": True,
        "task_id": task_id,
        "impacted_pages": impacted_pages,
    }


def execute_promote(vault_path: str, task_id: int) -> dict[str, Any]:
    """Execute a confirmed promotion task.

    Expected payload:
      {"concept": "<slug>", ...}
    """
    task = _load_task(vault_path, task_id)
    if "error" in task:
        return task
    if task["status"] == "done":
        return {"already_applied": True, "task_id": task_id, "completed": True}
    if task["status"] not in {"confirmed", "processing"}:
        return {"error": f"Task {task_id} must be confirmed before execution"}

    concept_id = task["payload"].get("concept", "")
    if not concept_id:
        return block_task(vault_path, task_id, "promotion task missing concept")

    current = get_concept(vault_path, concept_id)
    if current and current["type"] == "topic":
        complete_task(vault_path, task_id)
        return {"already_applied": True, "task_id": task_id, "completed": True}

    conn = get_db(vault_path)
    conn.execute(
        "UPDATE maintenance_queue SET status = 'processing' WHERE id = ?",
        (task_id,),
    )
    conn.commit()

    result = promote_concept(vault_path, concept_id)
    if "error" in result:
        return fail_task(vault_path, task_id, result["error"])

    topic = get_concept(vault_path, concept_id)
    dep_version = topic["version"] if topic else 1
    conn.execute(
        """UPDATE compile_deps
           SET dep_type = 'topic', dep_version = ?
           WHERE dep_id = ?""",
        (dep_version, concept_id),
    )
    conn.commit()

    _promote_concept_page_to_topic(vault_path, concept_id)
    impacted_pages = _dependent_pages_for_ids(conn, [concept_id])
    for page in impacted_pages:
        _rewrite_page_links(vault_path, page["page_id"], page["page_type"], concept_id, concept_id, to_section="topics")
    refresh_summary = _refresh_topic_page(vault_path, concept_id)
    complete_task(vault_path, task_id)
    return {
        **result,
        "completed": True,
        "task_id": task_id,
        "impacted_pages": impacted_pages,
        "refresh": refresh_summary,
    }


def execute_refresh(vault_path: str, task_id: int) -> dict[str, Any]:
    """Execute a confirmed refresh task.

    Current Phase 3A behavior is conservative: if the target page does not
    exist, the task is blocked.  If it exists, the task is marked complete and
    returns impacted page metadata for the next write stage/controller pass.
    """
    task = _load_task(vault_path, task_id)
    if "error" in task:
        return task
    if task["status"] == "done":
        return {"already_applied": True, "task_id": task_id, "completed": True}
    if task["status"] not in {"confirmed", "processing"}:
        return {"error": f"Task {task_id} must be confirmed before execution"}

    payload = task["payload"]
    topic = payload.get("topic", "")
    if not topic:
        return block_task(vault_path, task_id, "refresh task missing topic")

    topic_path = os.path.join(vault_path, "Paper Distill", "wiki", "topics", f"{topic}.md")
    if not os.path.exists(topic_path):
        return block_task(vault_path, task_id, f"topic page not found: {topic}")

    conn = get_db(vault_path)
    impacted_pages = _dependent_pages_for_ids(conn, [topic])
    refresh_summary = _refresh_topic_page(vault_path, topic)
    complete_task(vault_path, task_id)
    return {
        "completed": True,
        "task_id": task_id,
        "topic": topic,
        "impacted_pages": impacted_pages,
        "refresh": refresh_summary,
    }


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
    if task_type == "merge_candidate" and ("file_a" in payload or "file_b" in payload):
        pair = sorted([payload.get("file_a", ""), payload.get("file_b", "")])
        return f"merge:{pair[0]}|{pair[1]}"
    if task_type == "paper_duplicate_review":
        pair = sorted([payload.get("file_a", ""), payload.get("file_b", "")])
        return f"paper-dup:{pair[0]}|{pair[1]}"
    if task_type == "merge_candidate":
        return f"concept-merge:{payload.get('from_id', '')}|{payload.get('to_id', '')}"
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


def _load_task(vault_path: str, task_id: int) -> dict[str, Any]:
    conn = get_db(vault_path)
    row = conn.execute(
        "SELECT * FROM maintenance_queue WHERE id = ?",
        (task_id,),
    ).fetchone()
    if not row:
        return {"error": f"Task {task_id} not found"}
    task = dict(row)
    try:
        task["payload"] = json.loads(task["payload"])
    except (json.JSONDecodeError, TypeError):
        task["payload"] = {}
    return task


def _dependent_pages_for_ids(conn, dep_ids: list[str]) -> list[dict[str, Any]]:
    if not dep_ids:
        return []
    placeholders = ", ".join("?" for _ in dep_ids)
    rows = conn.execute(
        f"""SELECT DISTINCT page_id, page_type
            FROM compile_deps
            WHERE dep_id IN ({placeholders})
            ORDER BY page_type, page_id""",
        dep_ids,
    ).fetchall()
    return [dict(row) for row in rows]


_PAGE_PATHS = {
    "paper": ("wiki", "papers"),
    "concept": ("wiki", "concepts"),
    "method": ("wiki", "methods"),
    "topic": ("wiki", "topics"),
}


def _page_path(vault_path: str, page_id: str, page_type: str) -> str:
    parts = _PAGE_PATHS[page_type]
    return os.path.join(vault_path, "Paper Distill", *parts, f"{page_id}.md")


def _rewrite_page_links(
    vault_path: str,
    page_id: str,
    page_type: str,
    from_id: str,
    to_id: str,
    *,
    to_section: str = "concepts",
) -> None:
    if page_type not in _PAGE_PATHS:
        return
    path = _page_path(vault_path, page_id, page_type)
    if not os.path.exists(path):
        return

    raw = open(path, "r", encoding="utf-8").read()
    frontmatter, body = _split_markdown(raw)
    main_body, user_suffix = _split_user_body(body)

    main_body = _replace_wikilinks(main_body, from_id, to_id, to_section=to_section)
    if page_type in {"paper", "concept", "topic"}:
        concepts = frontmatter.get("concepts", [])
        if isinstance(concepts, str):
            concepts = [concepts]
        concepts = [to_id if slugify(str(item)) == from_id else item for item in concepts]
        if concepts:
            frontmatter["concepts"] = concepts
        topics = frontmatter.get("topics", [])
        if isinstance(topics, str):
            topics = [topics]
        topics = [to_id if slugify(str(item)) == from_id and to_section == "topics" else item for item in topics]
        if topics:
            frontmatter["topics"] = topics

    rebuilt = main_body.strip()
    if user_suffix:
        rebuilt = f"{rebuilt}\n\n{user_suffix}".strip()
    with open(path, "w", encoding="utf-8") as f:
        f.write(_render_markdown(frontmatter, rebuilt))


def _promote_concept_page_to_topic(vault_path: str, concept_id: str) -> None:
    concept_path = _page_path(vault_path, concept_id, "concept")
    if not os.path.exists(concept_path):
        return
    content = open(concept_path, "r", encoding="utf-8").read()
    frontmatter, body = _split_markdown(content)
    topic_path = _page_path(vault_path, concept_id, "topic")
    os.makedirs(os.path.dirname(topic_path), exist_ok=True)
    with open(topic_path, "w", encoding="utf-8") as f:
        f.write(_render_markdown(frontmatter, body))
    with open(concept_path, "w", encoding="utf-8") as f:
        f.write(
            _render_markdown(
                {"concept": concept_id, "redirect_to": f"topics/{concept_id}"},
                f"# {frontmatter.get('concept', concept_id)}\n\nPromoted to [[topics/{concept_id}]].",
            )
        )


def _refresh_topic_page(vault_path: str, topic_id: str) -> dict[str, Any]:
    conn = get_db(vault_path)
    papers = conn.execute(
        """SELECT DISTINCT page_id
           FROM compile_deps
           WHERE dep_id = ? AND page_type = 'paper'""",
        (topic_id,),
    ).fetchall()
    concepts = conn.execute(
        """SELECT DISTINCT dep_id
           FROM compile_deps
           WHERE page_type = 'paper' AND dep_type = 'concept'""",
    ).fetchall()

    paper_ids = [row["page_id"] for row in papers]
    concept_ids = sorted({row["dep_id"] for row in concepts if row["dep_id"] != topic_id})[:20]
    topic = get_concept(vault_path, topic_id) or {"canonical": topic_id, "version": 1}

    frontmatter = {
        "topic": topic_id,
        "title": topic.get("canonical", topic_id),
        "compile_version": topic.get("version", 1),
        "last_compiled": _now_iso(),
    }
    content = "\n\n".join(
        [
            "<!-- managed:start section=overview -->",
            "## Overview",
            f"{topic.get('canonical', topic_id)} currently connects {len(paper_ids)} compiled papers in the vault.",
            "<!-- managed:end section=overview -->",
            "<!-- managed:start section=representative-papers -->",
            "## Representative Papers",
            *([f"- [[papers/{paper_id}]]" for paper_id in paper_ids[:20]] or ["- None linked yet."]),
            "<!-- managed:end section=representative-papers -->",
            "<!-- managed:start section=related-concepts -->",
            "## Related Concepts",
            *([f"- [[concepts/{concept_id}]]" for concept_id in concept_ids[:20]] or ["- None linked yet."]),
            "<!-- managed:end section=related-concepts -->",
            "<!-- managed:start section=recent-developments -->",
            "## Recent Developments",
            f"- Refreshed at {_now_iso()}",
            "<!-- managed:end section=recent-developments -->",
        ]
    )
    result = commit_compile_result(
        vault_path,
        topic_id,
        "topic",
        content,
        frontmatter,
        deps=[{"dep_type": "topic", "dep_id": topic_id, "dep_version": topic.get("version", 1)}],
    )
    return result


def _split_markdown(content: str) -> tuple[dict[str, Any], str]:
    if not content.startswith("---\n"):
        return {}, content
    _, remainder = content.split("---\n", 1)
    fm_text, body = remainder.split("\n---\n", 1)
    return yaml.safe_load(fm_text) or {}, body.lstrip()


def _render_markdown(frontmatter: dict[str, Any], body: str) -> str:
    return f"---\n{yaml.safe_dump(frontmatter, sort_keys=False, allow_unicode=True).strip()}\n---\n\n{body.strip()}\n"


def _split_user_body(body: str) -> tuple[str, str]:
    match = re.search(r"^##\s+(My Notes|Reading Notes)\b", body, re.MULTILINE)
    if not match:
        return body.strip(), ""
    return body[: match.start()].strip(), body[match.start() :].strip()


def _replace_wikilinks(text: str, from_id: str, to_id: str, *, to_section: str) -> str:
    pattern = re.compile(rf"\[\[(concepts|topics)/{re.escape(from_id)}(?:\|([^\]]+))?\]\]")

    def repl(match: re.Match[str]) -> str:
        label = match.group(2)
        if label:
            return f"[[{to_section}/{to_id}|{label}]]"
        return f"[[{to_section}/{to_id}]]"

    return pattern.sub(repl, text)
