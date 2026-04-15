from __future__ import annotations

import json
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

SCOPE_TO_COLLECTIONS: dict[str, tuple[str, ...]] = {
    "canon": ("canon-papers", "canon-concepts"),
    "insights": ("insights-conversations", "insights-ideas"),
    "raw": ("raw-evidence",),
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


def ensure_qmd_ready(vault_path: Path) -> dict[str, object]:
    collections = _run_qmd(["collection", "list"]).stdout
    contexts = _run_qmd(["context", "list"]).stdout

    for name, (rel_path, context) in COLLECTIONS.items():
        if not _list_contains(collections, name):
            _run_qmd(["collection", "add", str(vault_path / rel_path), "--name", name])
        if not _list_contains(contexts, f"qmd://{name}"):
            _run_qmd(["context", "add", f"qmd://{name}", context])

    return {"ready": True, "collections": list(COLLECTIONS.keys())}


def qmd_ready_report(vault_path: Path) -> dict[str, object]:
    try:
        result = _run_qmd(["collection", "list"])
    except FileNotFoundError:
        return {"status": "not_ready", "reason": "qmd binary not found"}
    except subprocess.CalledProcessError as exc:
        return {"status": "not_ready", "reason": exc.stderr.strip() or "qmd unavailable"}

    missing = [name for name in COLLECTIONS if not _list_contains(result.stdout, name)]
    if missing:
        return {"status": "degraded", "reason": "missing qmd collections", "missing": missing}
    return {"status": "ready", "reason": "qmd collections available"}


def qmd_search(vault_path: Path, query: str, scope: str) -> dict[str, object]:
    ready = qmd_ready_report(vault_path)
    if ready["status"] == "not_ready":
        return {"status": "not_ready", "error": ready["reason"]}

    collections = SCOPE_TO_COLLECTIONS.get(scope)
    if collections is None:
        return {"status": "error", "error": f"unsupported scope: {scope}"}

    args = ["query", query, "--json"]
    for collection in collections:
        args.extend(["-c", collection])

    result = _run_qmd(args)
    try:
        parsed = json.loads(result.stdout or "null")
    except json.JSONDecodeError as exc:
        return {"status": "error", "error": f"invalid qmd JSON: {exc.msg}"}
    return {"status": "ok", "scope": scope, "qmd_context": scope, "results": parsed}


def qmd_get(vault_path: Path, id_or_path: str) -> dict[str, object]:
    candidate = Path(id_or_path)
    if not candidate.exists():
        matches = sorted(vault_path.rglob(id_or_path))
        if not matches and not id_or_path.endswith(".md"):
            matches = sorted(vault_path.rglob(f"{id_or_path}.md"))
        if not matches:
            return {"status": "missing", "error": f"document not found: {id_or_path}"}
        candidate = matches[0]

    result = _run_qmd(["get", str(candidate)])
    return {"status": "ok", "path": str(candidate), "body": result.stdout}


def qmd_update(vault_path: Path) -> dict[str, object]:
    try:
        result = _run_qmd(["update"])
    except subprocess.CalledProcessError as exc:
        return {"ok": False, "error": exc.stderr.strip() or "qmd update failed"}
    return {"ok": True, "stdout": result.stdout}


def qmd_reembed_force(vault_path: Path) -> dict[str, object]:
    try:
        result = _run_qmd(["embed", "-f"])
    except subprocess.CalledProcessError as exc:
        return {"ok": False, "error": exc.stderr.strip() or "qmd embed failed"}
    return {"ok": True, "stdout": result.stdout}
