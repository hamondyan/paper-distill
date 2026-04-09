"""Shared durable publish primitive for compiled page bundles."""
from __future__ import annotations

import json
import os
import shutil
import uuid
from pathlib import Path
from typing import Any

from server.database import _now_iso


def begin_publish_run(
    conn: Any,
    *,
    mutation_id: int,
    target_key: str,
    operation: str,
    bundle: dict[str, Any],
) -> dict[str, Any]:
    """Create a new publish run unless one is already in-flight or published."""
    existing = conn.execute(
        """
        SELECT *
        FROM publish_journal
        WHERE mutation_id = ?
          AND state IN ('started', 'staged', 'published')
        ORDER BY started_at DESC, run_id DESC
        LIMIT 1
        """,
        (mutation_id,),
    ).fetchone()
    if existing:
        return _decode_run(existing)

    now = _now_iso()
    run_id = uuid.uuid4().hex
    conn.execute(
        """
        INSERT INTO publish_journal
            (run_id, mutation_id, target_key, operation, state, bundle_json,
             started_at, updated_at)
        VALUES (?, ?, ?, ?, 'started', ?, ?, ?)
        """,
        (
            run_id,
            mutation_id,
            target_key,
            operation,
            json.dumps(bundle, ensure_ascii=False, sort_keys=True),
            now,
            now,
        ),
    )
    conn.commit()
    return get_publish_run(conn, run_id)


def get_publish_run(conn: Any, run_id: str) -> dict[str, Any]:
    row = conn.execute(
        "SELECT * FROM publish_journal WHERE run_id = ?",
        (run_id,),
    ).fetchone()
    return _decode_run(row)


def get_latest_publish_run(conn: Any, mutation_id: int) -> dict[str, Any]:
    row = conn.execute(
        """
        SELECT *
        FROM publish_journal
        WHERE mutation_id = ?
        ORDER BY started_at DESC, run_id DESC
        LIMIT 1
        """,
        (mutation_id,),
    ).fetchone()
    return _decode_run(row)


def stage_publish_run(vault_path: str, conn: Any, run: dict[str, Any]) -> dict[str, Any]:
    """Materialize the bundle into a durable staged area and mark the run staged."""
    bundle = run.get("bundle") or {}
    stage_root = _stage_root(vault_path, run["run_id"])
    manifest: list[dict[str, str]] = []

    stage_root.mkdir(parents=True, exist_ok=True)
    for file_spec in bundle.get("files", []):
        final_relpath = str(file_spec["dest_relpath"])
        staged_relpath = str(Path("bundle") / final_relpath)
        staged_path = stage_root / staged_relpath
        _atomic_write_text(staged_path, str(file_spec["content"]))
        manifest.append(
            {
                "dest_relpath": final_relpath,
                "staged_relpath": staged_relpath,
            }
        )

    now = _now_iso()
    conn.execute(
        """
        UPDATE publish_journal
        SET state = 'staged',
            staged_root = ?,
            staged_manifest_json = ?,
            staged_at = COALESCE(staged_at, ?),
            updated_at = ?
        WHERE run_id = ?
        """,
        (
            str(stage_root),
            json.dumps(manifest, ensure_ascii=False, sort_keys=True),
            now,
            now,
            run["run_id"],
        ),
    )
    conn.commit()
    return get_publish_run(conn, run["run_id"])


def apply_staged_bundle(vault_path: str, run: dict[str, Any]) -> None:
    """Atomically promote staged files into their final visible locations."""
    stage_root = Path(run["staged_root"])
    manifest = run.get("staged_manifest") or []
    bundle = run.get("bundle") or {}
    bundle_by_path = {
        str(item["dest_relpath"]): item for item in bundle.get("files", [])
    }

    for item in manifest:
        final_relpath = str(item["dest_relpath"])
        staged_path = stage_root / str(item["staged_relpath"])
        final_path = Path(vault_path).expanduser() / final_relpath
        if not staged_path.exists():
            fallback = bundle_by_path.get(final_relpath)
            if fallback is None:
                raise FileNotFoundError(f"Missing staged file for {final_relpath}")
            _atomic_write_text(staged_path, str(fallback["content"]))
        final_path.parent.mkdir(parents=True, exist_ok=True)
        os.replace(staged_path, final_path)


def mark_publish_run_published(conn: Any, run_id: str) -> dict[str, Any]:
    now = _now_iso()
    conn.execute(
        """
        UPDATE publish_journal
        SET state = 'published',
            published_at = COALESCE(published_at, ?),
            error = NULL,
            updated_at = ?
        WHERE run_id = ?
        """,
        (now, now, run_id),
    )
    conn.commit()
    return get_publish_run(conn, run_id)


def mark_publish_run_failed(conn: Any, run_id: str, error: str) -> dict[str, Any]:
    now = _now_iso()
    conn.execute(
        """
        UPDATE publish_journal
        SET state = 'failed',
            error = ?,
            failed_at = COALESCE(failed_at, ?),
            updated_at = ?
        WHERE run_id = ?
        """,
        (error, now, now, run_id),
    )
    conn.commit()
    return get_publish_run(conn, run_id)


def cleanup_staged_publish_run(run: dict[str, Any]) -> None:
    staged_root = run.get("staged_root")
    if staged_root:
        shutil.rmtree(staged_root, ignore_errors=True)


def _stage_root(vault_path: str, run_id: str) -> Path:
    root = Path(vault_path).expanduser() / "Paper Distill" / ".state" / "publish" / "staging"
    return root / run_id


def _atomic_write_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = path.with_name(f".{path.name}.{uuid.uuid4().hex}.tmp")
    tmp_path.write_text(content, encoding="utf-8")
    os.replace(tmp_path, path)


def _decode_run(row: Any) -> dict[str, Any]:
    if not row:
        return {}
    decoded = dict(row)
    decoded["bundle"] = _decode_json(decoded.get("bundle_json"))
    manifest = _decode_json(decoded.get("staged_manifest_json"))
    decoded["staged_manifest"] = manifest if isinstance(manifest, list) else []
    return decoded


def _decode_json(raw: Any) -> Any:
    if not raw:
        return {}
    try:
        return json.loads(raw)
    except (TypeError, json.JSONDecodeError):
        return {}
