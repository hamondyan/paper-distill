from __future__ import annotations

import re
import subprocess
from pathlib import Path

from server.config import get_qmd_binary

COLLECTIONS: dict[str, tuple[str, str]] = {
    "canon-papers": ("wiki/papers", "Canonical distilled papers"),
    "canon-concepts": ("wiki/concepts", "Canonical concept pages"),
    "insights-conversations": ("insights/conversations", "Conversation-derived research insights"),
    "insights-ideas": ("insights/ideas", "Idea drafts and later validation assets"),
    "raw-evidence": ("raw/evidence", "Raw captured evidence and source markdown"),
}


def _run_qmd(args: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [get_qmd_binary(), *args],
        check=True,
        capture_output=True,
        text=True,
    )


def _list_contains(stdout: str, needle: str) -> bool:
    return any(needle in line for line in stdout.splitlines())


def _normalize_path(value: Path | str) -> Path:
    return Path(value).expanduser().resolve()


def _collection_path_from_show(stdout: str) -> Path | None:
    for line in stdout.splitlines():
        match = re.match(r"^\s*Path:\s*(.+?)\s*$", line)
        if match:
            return _normalize_path(match.group(1))
    return None


def _collection_mount_matches(vault_path: Path, rel_path: str, show_stdout: str) -> bool:
    expected = _normalize_path(vault_path / rel_path)
    actual = _collection_path_from_show(show_stdout)
    return actual is not None and actual == expected


def _collection_show(name: str) -> subprocess.CompletedProcess[str]:
    return _run_qmd(["collection", "show", name])


def _ensure_collection_for_vault(vault_path: Path, name: str, rel_path: str) -> bool:
    try:
        result = _collection_show(name)
    except (FileNotFoundError, subprocess.CalledProcessError):
        _run_qmd(["collection", "add", str(vault_path / rel_path), "--name", name])
        return True

    if not _collection_mount_matches(vault_path, rel_path, result.stdout):
        _run_qmd(["collection", "remove", name])
        _run_qmd(["collection", "add", str(vault_path / rel_path), "--name", name])
        return True
    return False


def ensure_qmd_ready(vault_path: Path) -> dict[str, object]:
    contexts = _run_qmd(["context", "list"]).stdout

    for name, (rel_path, context) in COLLECTIONS.items():
        remounted = _ensure_collection_for_vault(vault_path, name, rel_path)
        if remounted:
            contexts = _run_qmd(["context", "list"]).stdout
        if not _list_contains(contexts, f"qmd://{name}"):
            _run_qmd(["context", "add", f"qmd://{name}", context])

    return {"ready": True, "collections": list(COLLECTIONS.keys())}


def qmd_ready_report(vault_path: Path) -> dict[str, object]:
    try:
        _run_qmd(["collection", "list"])
    except FileNotFoundError:
        return {"status": "not_ready", "reason": "qmd binary not found"}
    except subprocess.CalledProcessError as exc:
        return {"status": "not_ready", "reason": exc.stderr.strip() or "qmd unavailable"}

    missing: list[str] = []
    for name, (rel_path, _context) in COLLECTIONS.items():
        try:
            show = _collection_show(name)
        except (FileNotFoundError, subprocess.CalledProcessError):
            missing.append(name)
            continue
        if not _collection_mount_matches(vault_path, rel_path, show.stdout):
            missing.append(name)

    if missing:
        return {"status": "degraded", "reason": "missing qmd collections", "missing": missing}
    return {"status": "ready", "reason": "qmd collections available"}
