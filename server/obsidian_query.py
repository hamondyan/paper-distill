"""Obsidian-first query adapter with filesystem fallback."""
from __future__ import annotations

import json
import os
import shutil
import subprocess
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

from server.config import get_paper_distill_settings
from server.vault_contract import DEFAULT_QUERY_SECTIONS, query_section_paths
from server.vault_query import _COMPACT_STRIP_FIELDS, _derive_preview_text, _sort_key_for_item, query_vault_sync

_CAPABILITIES = {
    "official_cli": ["list", "property_filters", "tag_filters", "keyword_search"],
    "filesystem_scan": ["list", "property_filters", "tag_filters", "keyword_search"],
}


def available_obsidian_query_providers() -> list[dict[str, Any]]:
    providers: list[dict[str, Any]] = []

    if shutil.which("obsidian"):
        providers.append(
            {
                "name": "official_cli",
                "label": "Obsidian CLI",
                "capabilities": list(_CAPABILITIES["official_cli"]),
            }
        )
    return providers


def _query_with_provider(
    provider_name: str,
    vault_path: str,
    *,
    section: str = "all",
    topic: str | None = None,
    uncompiled_only: bool = False,
    status: str | None = None,
    detail: str = "compact",
    limit: int | None = None,
    sort_by: str = "updated_at",
    days_back: int | None = None,
) -> dict[str, Any]:
    if provider_name == "official_cli":
        return _query_with_official_cli(
            provider_name,
            vault_path,
            section=section,
            topic=topic,
            uncompiled_only=uncompiled_only,
            status=status,
            detail=detail,
            limit=limit,
            sort_by=sort_by,
            days_back=days_back,
        )
    raise RuntimeError(f"Unsupported Obsidian query provider: {provider_name}")


def _query_with_official_cli(
    provider_name: str,
    vault_path: str,
    **query: Any,
) -> dict[str, Any]:
    settings = get_paper_distill_settings().get("obsidian_query", {})
    command = settings.get("command")
    if not command:
        binary = shutil.which("obsidian")
        if not binary:
            raise RuntimeError("official_cli provider requires the obsidian executable")
        if not _is_open_obsidian_vault(vault_path):
            raise RuntimeError("official_cli provider requires vault_path to be open in Obsidian")
        return _query_with_native_official_cli(binary, vault_path, **query)

    command_parts = [command] if isinstance(command, str) else [str(part) for part in command]
    completed = subprocess.run(
        command_parts,
        check=True,
        capture_output=True,
        text=True,
        input=json.dumps({"vault_path": vault_path, "provider": provider_name, **query}, ensure_ascii=False),
    )
    result = json.loads(completed.stdout or "{}")
    if not isinstance(result, dict):
        raise RuntimeError(f"{provider_name} returned a non-object payload")
    return result


def _obsidian_config_paths() -> list[Path]:
    paths = [
        Path.home() / "Library" / "Application Support" / "obsidian" / "obsidian.json",
        Path.home() / ".config" / "obsidian" / "obsidian.json",
    ]
    appdata = os.environ.get("APPDATA")
    if appdata:
        paths.append(Path(appdata) / "obsidian" / "obsidian.json")
    return paths


def _is_open_obsidian_vault(vault_path: str) -> bool:
    try:
        target = Path(vault_path).expanduser().resolve()
    except OSError:
        return False

    for config_path in _obsidian_config_paths():
        try:
            payload = json.loads(config_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        vaults = payload.get("vaults", {})
        if not isinstance(vaults, dict):
            continue
        for vault in vaults.values():
            if not isinstance(vault, dict) or not vault.get("open"):
                continue
            configured_path = str(vault.get("path") or "").strip()
            if not configured_path:
                continue
            try:
                if Path(configured_path).expanduser().resolve() == target:
                    return True
            except OSError:
                continue
    return False


def _run_obsidian_cli(binary: str, *args: str) -> str:
    completed = subprocess.run(
        [binary, *args],
        check=True,
        capture_output=True,
        text=True,
        timeout=15.0,
    )
    return completed.stdout.strip()


def _parse_cli_paths(output: str) -> list[str]:
    paths: list[str] = []
    for line in output.splitlines():
        path = line.strip()
        if not path or path.lower().startswith("no "):
            continue
        paths.append(path)
    return paths


def _normalise_cli_path(vault_path: str, path: str) -> str:
    candidate = Path(path)
    if candidate.is_absolute():
        try:
            return os.path.relpath(candidate, vault_path).replace(os.sep, "/")
        except ValueError:
            return path
    return path.replace("\\", "/")


def _read_cli_properties(binary: str, path: str) -> dict[str, Any] | None:
    output = _run_obsidian_cli(binary, "properties", f"path={path}", "format=json")
    try:
        payload = json.loads(output or "{}")
    except json.JSONDecodeError:
        if output.lower().startswith("no "):
            return None
        raise
    if not isinstance(payload, dict) or not payload:
        return None
    return dict(payload)


def _query_with_native_official_cli(
    binary: str,
    vault_path: str,
    *,
    section: str = "all",
    topic: str | None = None,
    uncompiled_only: bool = False,
    status: str | None = None,
    detail: str = "compact",
    limit: int | None = None,
    sort_by: str = "updated_at",
    days_back: int | None = None,
) -> dict[str, Any]:
    sections = list(DEFAULT_QUERY_SECTIONS) if section == "all" else [section]
    result: dict[str, Any] = {"stats": {}, "sections": {}}

    cutoff_date: str | None = None
    if days_back is not None and days_back > 0:
        cutoff_date = (datetime.now() - timedelta(days=days_back)).isoformat()

    for sec in sections:
        rel_paths = list(query_section_paths(sec))
        if not rel_paths:
            continue

        items: list[dict[str, Any]] = []
        seen: set[str] = set()
        for rel_path in rel_paths:
            output = _run_obsidian_cli(binary, "files", f"folder={rel_path}")
            for cli_path in _parse_cli_paths(output):
                normalized_path = _normalise_cli_path(vault_path, cli_path)
                if normalized_path in seen:
                    continue
                if not normalized_path.endswith(".md") or Path(normalized_path).name == "_index.md":
                    continue
                seen.add(normalized_path)

                fm = _read_cli_properties(binary, normalized_path)
                if fm is None:
                    continue

                if topic:
                    paper_topics = fm.get("topics", fm.get("matched_topics", []))
                    if isinstance(paper_topics, str):
                        paper_topics = [paper_topics]
                    if topic not in paper_topics:
                        continue

                if status and str(fm.get("status", "")).strip().lower() != status.lower():
                    continue

                if uncompiled_only and fm.get("compiled") is True:
                    continue

                fm["_path"] = normalized_path
                try:
                    fm["_mtime"] = datetime.fromtimestamp(
                        os.path.getmtime(os.path.join(vault_path, normalized_path))
                    ).isoformat()
                except OSError:
                    fm["_mtime"] = ""

                if cutoff_date:
                    sort_val = _sort_key_for_item(fm, sort_by)
                    if sort_val and sort_val < cutoff_date:
                        continue

                items.append(fm)

        items.sort(key=lambda item: _sort_key_for_item(item, sort_by), reverse=True)

        if limit is not None and limit > 0:
            items = items[:limit]

        if detail == "compact":
            for item in items:
                item["preview_text"] = _derive_preview_text(item)
                for field in _COMPACT_STRIP_FIELDS:
                    item.pop(field, None)

        if sort_by != "_mtime":
            for item in items:
                item.pop("_mtime", None)

        result["stats"][sec] = len(items)
        result["sections"][sec] = items

    return result


def query_library_sync(
    vault_path: str,
    section: str = "all",
    topic: str | None = None,
    uncompiled_only: bool = False,
    status: str | None = None,
    detail: str = "compact",
    limit: int | None = None,
    sort_by: str = "updated_at",
    days_back: int | None = None,
) -> dict[str, Any]:
    providers = available_obsidian_query_providers()
    query_kwargs = {
        "section": section,
        "topic": topic,
        "uncompiled_only": uncompiled_only,
        "status": status,
        "detail": detail,
        "limit": limit,
        "sort_by": sort_by,
        "days_back": days_back,
    }

    for provider in providers:
        try:
            result = _query_with_provider(provider["name"], vault_path, **query_kwargs)
        except Exception:
            continue
        if isinstance(result, dict):
            result = dict(result)
            result["provider"] = provider["name"]
            result["fallback_used"] = False
            result["capabilities"] = list(provider.get("capabilities", []))
            result["available_providers"] = [item["name"] for item in providers]
            return result

    result = query_vault_sync(vault_path, **query_kwargs)
    result["provider"] = "filesystem_scan"
    result["fallback_used"] = True
    result["capabilities"] = list(_CAPABILITIES["filesystem_scan"])
    result["available_providers"] = [item["name"] for item in providers]
    return result
