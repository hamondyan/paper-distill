"""SQLite persistence layer for Paper Distill.

Manages the `.state/paper-distill.db` database that backs:
  - Concept Canonical Registry  (authority layer)
  - Compile State & Dependencies (rebuildable index layer)
  - Maintenance Queue           (authority layer)

The DB lives under ``Paper Distill/.state/`` inside the vault and is
excluded from version control (.gitignore).  Authority-layer tables
can be exported to JSON for backup; index-layer tables can be rebuilt
from vault files + compiled IR.
"""
from __future__ import annotations

import json
import logging
import os
import sqlite3
import threading
from pathlib import Path
from typing import Any

LOG = logging.getLogger(__name__)


def _now_iso() -> str:
    """Return current UTC-local time as an ISO-8601 string (seconds precision)."""
    from datetime import datetime
    return datetime.now().isoformat(timespec="seconds")

_PAPER_DISTILL_ROOT = "Paper Distill"
_STATE_DIR = ".state"
_DB_NAME = "paper-distill.db"

# Thread-local singleton connections keyed by vault_path
_lock = threading.Lock()
_connections: dict[str, sqlite3.Connection] = {}

# ---------------------------------------------------------------------------
# Schema
# ---------------------------------------------------------------------------

_SCHEMA_SQL = """
-- ===================== Authority Layer =====================

-- Concept Canonical Registry
CREATE TABLE IF NOT EXISTS concept_registry (
    id            TEXT PRIMARY KEY,       -- slug, e.g. "vision-language-action"
    canonical     TEXT NOT NULL,          -- display name, e.g. "Vision-Language-Action Models"
    type          TEXT NOT NULL,          -- concept | method | topic
    version       INTEGER DEFAULT 1,     -- incremented on substantive update
    promoted      BOOLEAN DEFAULT 0,
    paper_count   INTEGER DEFAULT 0,
    created_at    TEXT NOT NULL,
    updated_at    TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS concept_aliases (
    alias         TEXT PRIMARY KEY,       -- normalised surface form
    concept_id    TEXT NOT NULL,
    FOREIGN KEY (concept_id) REFERENCES concept_registry(id)
);

CREATE TABLE IF NOT EXISTS concept_merge_history (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    from_concept  TEXT NOT NULL,
    to_concept    TEXT NOT NULL,
    merged_at     TEXT NOT NULL,
    reason        TEXT
);

-- Maintenance Queue
CREATE TABLE IF NOT EXISTS maintenance_queue (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    task_type   TEXT NOT NULL,            -- merge_candidate | promote_to_topic
                                         -- | stale_topic_refresh | orphan_fix
    payload     TEXT NOT NULL,            -- JSON with operation params
    confidence  REAL,                     -- 0.0 ~ 1.0
    status      TEXT DEFAULT 'pending',   -- pending | confirmed | processing
                                         -- | done | rejected
    created_at  TEXT NOT NULL,
    resolved_at TEXT
);

-- ===================== Rebuildable Index Layer =====================

-- Compile State (generic page_id + page_type)
CREATE TABLE IF NOT EXISTS compile_state (
    page_id           TEXT NOT NULL,
    page_type         TEXT NOT NULL,      -- paper | concept | method | topic
    compile_version   INTEGER NOT NULL,
    schema_version    TEXT NOT NULL,      -- e.g. "2024-06"
    compiled_at       TEXT NOT NULL,
    ir_path           TEXT,              -- points to compiled_ir/ JSON
    content_hash      TEXT,              -- hash of managed sections for conflict detect
    PRIMARY KEY (page_id, page_type)
);

-- Compile Dependencies
CREATE TABLE IF NOT EXISTS compile_deps (
    page_id       TEXT NOT NULL,
    page_type     TEXT NOT NULL,
    dep_type      TEXT NOT NULL,         -- concept | method | topic
    dep_id        TEXT NOT NULL,
    dep_version   INTEGER NOT NULL,      -- matches concept_registry.version at compile time
    FOREIGN KEY (page_id, page_type) REFERENCES compile_state(page_id, page_type),
    FOREIGN KEY (dep_id) REFERENCES concept_registry(id)
);

-- Index on deps for reverse lookups  ("who depends on concept X?")
CREATE INDEX IF NOT EXISTS idx_compile_deps_dep
    ON compile_deps(dep_id, dep_type);
"""


# ---------------------------------------------------------------------------
# Connection management
# ---------------------------------------------------------------------------

def _db_path(vault_path: str) -> Path:
    """Return the absolute path to the SQLite database file."""
    return (
        Path(vault_path).expanduser()
        / _PAPER_DISTILL_ROOT
        / _STATE_DIR
        / _DB_NAME
    )


def get_db(vault_path: str) -> sqlite3.Connection:
    """Return a singleton SQLite connection for *vault_path*.

    Thread-safe.  Uses WAL mode for concurrent reads.
    """
    key = str(Path(vault_path).expanduser().resolve())
    if key in _connections:
        return _connections[key]

    with _lock:
        # Double-check under lock
        if key in _connections:
            return _connections[key]

        db_file = _db_path(vault_path)
        db_file.parent.mkdir(parents=True, exist_ok=True)

        conn = sqlite3.connect(str(db_file), check_same_thread=False)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA foreign_keys=ON")
        conn.executescript(_SCHEMA_SQL)
        conn.commit()

        _connections[key] = conn
        LOG.info("Opened database at %s", db_file)
        return conn


def close_db(vault_path: str) -> None:
    """Close and remove the cached connection for *vault_path*."""
    key = str(Path(vault_path).expanduser().resolve())
    with _lock:
        conn = _connections.pop(key, None)
        if conn:
            conn.close()


def init_db(vault_path: str) -> Path:
    """Ensure the database file and tables exist.  Returns the DB path."""
    get_db(vault_path)
    return _db_path(vault_path)


# ---------------------------------------------------------------------------
# Export / Import (authority-layer backup)
# ---------------------------------------------------------------------------

_AUTHORITY_TABLES = (
    "concept_registry",
    "concept_aliases",
    "concept_merge_history",
    "maintenance_queue",
)


def export_authority_state(vault_path: str) -> dict[str, list[dict]]:
    """Export all authority-layer tables to a JSON-serialisable dict."""
    conn = get_db(vault_path)
    result: dict[str, list[dict]] = {}
    for table in _AUTHORITY_TABLES:
        rows = conn.execute(f"SELECT * FROM {table}").fetchall()
        result[table] = [dict(row) for row in rows]
    return result


def import_authority_state(vault_path: str, data: dict[str, list[dict]]) -> dict[str, int]:
    """Import authority-layer data from a previous export.

    Uses INSERT OR REPLACE to handle conflicts.  Returns per-table
    import counts.
    """
    conn = get_db(vault_path)
    counts: dict[str, int] = {}
    for table in _AUTHORITY_TABLES:
        rows = data.get(table, [])
        if not rows:
            counts[table] = 0
            continue
        cols = list(rows[0].keys())
        placeholders = ", ".join("?" for _ in cols)
        col_names = ", ".join(cols)
        for row in rows:
            conn.execute(
                f"INSERT OR REPLACE INTO {table} ({col_names}) VALUES ({placeholders})",
                [row.get(c) for c in cols],
            )
        conn.commit()
        counts[table] = len(rows)
    return counts
