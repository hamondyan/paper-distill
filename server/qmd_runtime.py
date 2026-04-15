from __future__ import annotations

import json
import subprocess
import re
from pathlib import Path

from server.config import get_qmd_binary

COLLECTIONS: dict[str, tuple[str, str]] = {
    "canon-papers": ("wiki/papers", "Canonical distilled papers"),
    "canon-concepts": ("wiki/concepts", "Canonical concept pages"),
    "insights-conversations": ("insights/conversations", "Conversation-derived research insights"),
    "insights-ideas": ("insights/ideas", "Idea drafts and later validation assets"),
    "raw-evidence": ("raw/evidence", "Raw captured evidence and source markdown"),
}

SCOPE_TO_COLLECTIONS: dict[str, tuple[str, ...]] = {
    "canon": ("canon-papers", "canon-concepts"),
    "insights": ("insights-conversations", "insights-ideas"),
    "raw": ("raw-evidence",),
}

LOOKUP_NAMESPACE_ORDER: tuple[str, ...] = (
    "wiki/papers",
    "wiki/concepts",
    "insights/conversations",
    "insights/ideas",
    "raw/evidence",
)

EXPLICIT_PATH_PREFIXES: tuple[str, ...] = (
    "wiki",
    "raw",
    "insights",
    "inbox",
    "exports",
    ".state",
)


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


def _stable_id_candidates(id_or_path: str) -> list[str]:
    candidates: list[str] = []
    raw = id_or_path.strip()
    if raw:
        candidates.append(raw)
    sanitized = raw.replace(":", "-").replace("/", "-")
    if sanitized and sanitized not in candidates:
        candidates.append(sanitized)
    return candidates


def _looks_like_explicit_path(id_or_path: str) -> bool:
    raw = id_or_path.strip()
    if not raw:
        return False
    candidate = Path(raw)
    if candidate.is_absolute():
        return True
    if raw.endswith(".md"):
        return True
    return candidate.parts[:1] and candidate.parts[0] in EXPLICIT_PATH_PREFIXES


def _find_stable_id_match(vault_path: Path, id_or_path: str) -> Path | None:
    for candidate in _stable_id_candidates(id_or_path):
        suffix = candidate[:-3] if candidate.endswith(".md") else candidate
        for rel_dir in LOOKUP_NAMESPACE_ORDER:
            base = vault_path / rel_dir
            if suffix:
                for match in sorted(base.rglob(f"*--{suffix}.md")):
                    if match.is_file():
                        return match
            for match in sorted(base.rglob(candidate)):
                if match.is_file():
                    return match
            if not candidate.endswith(".md"):
                for match in sorted(base.rglob(f"{candidate}.md")):
                    if match.is_file():
                        return match
    return None


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


def qmd_search(vault_path: Path, query: str, scope: str) -> dict[str, object]:
    ready = qmd_ready_report(vault_path)
    if ready["status"] != "ready":
        return {"status": ready["status"], "error": ready["reason"]}

    collections = SCOPE_TO_COLLECTIONS.get(scope)
    if collections is None:
        return {"status": "error", "error": f"unsupported scope: {scope}"}

    args = ["query", query, "--json"]
    for collection in collections:
        args.extend(["-c", collection])

    try:
        result = _run_qmd(args)
    except FileNotFoundError:
        return {"status": "not_ready", "error": "qmd binary not found"}
    except subprocess.CalledProcessError as exc:
        return {"status": "error", "error": exc.stderr.strip() or "qmd query failed"}
    try:
        parsed = json.loads(result.stdout or "null")
    except json.JSONDecodeError as exc:
        return {"status": "error", "error": f"invalid qmd JSON: {exc.msg}"}
    return {"status": "ok", "scope": scope, "qmd_context": scope, "results": parsed}


def qmd_get(vault_path: Path, id_or_path: str) -> dict[str, object]:
    candidate = Path(id_or_path)
    if _looks_like_explicit_path(id_or_path):
        explicit_path = candidate if candidate.is_absolute() else vault_path / candidate
        resolved_vault = _normalize_path(vault_path)
        resolved_explicit = _normalize_path(explicit_path)
        try:
            resolved_explicit.relative_to(resolved_vault)
        except ValueError:
            return {"status": "error", "error": f"path escapes vault: {id_or_path}"}

        if resolved_explicit.exists():
            candidate = resolved_explicit
        else:
            match = _find_stable_id_match(vault_path, id_or_path)
            if match is None:
                return {"status": "missing", "error": f"document not found: {id_or_path}"}
            candidate = match
    else:
        match = _find_stable_id_match(vault_path, id_or_path)
        if match is None:
            return {"status": "missing", "error": f"document not found: {id_or_path}"}
        candidate = match

    try:
        result = _run_qmd(["get", str(candidate)])
    except FileNotFoundError:
        return {"status": "not_ready", "reason": "qmd binary not found"}
    except subprocess.CalledProcessError as exc:
        return {"status": "error", "error": exc.stderr.strip() or "qmd get failed"}
    return {"status": "ok", "path": str(candidate), "body": result.stdout}


def qmd_update(vault_path: Path) -> dict[str, object]:
    try:
        result = _run_qmd(["update"])
    except FileNotFoundError:
        return {"ok": False, "error": "qmd binary not found"}
    except subprocess.CalledProcessError as exc:
        return {"ok": False, "error": exc.stderr.strip() or "qmd update failed"}
    return {"ok": True, "stdout": result.stdout}


def qmd_reembed_force(vault_path: Path) -> dict[str, object]:
    try:
        result = _run_qmd(["embed", "-f"])
    except FileNotFoundError:
        return {"ok": False, "error": "qmd binary not found"}
    except subprocess.CalledProcessError as exc:
        return {"ok": False, "error": exc.stderr.strip() or "qmd embed failed"}
    return {"ok": True, "stdout": result.stdout}
