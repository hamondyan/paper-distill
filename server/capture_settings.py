"""Configuration-reading helpers for capture, topic selection, and Zotero runtime.

All functions read from the live settings (server.config) and return plain
dicts or tuples. No file I/O, no MCP concerns.
"""
from __future__ import annotations

from pathlib import Path

from server.config import (
    get_env,
    get_paper_distill_settings,
    get_topics,
    get_zotero_collection_name,
    get_zotero_local_export_dir,
    get_zotero_mode,
    get_zotero_settings,
)


def _selected_topics(query: str | None, topic_keys: list[str] | None) -> dict[str, dict]:
    topics = get_topics()
    if query:
        return {
            "ad-hoc": {
                "label": query,
                "keywords": [query],
            }
        }
    if not topic_keys:
        return topics

    selected = {
        key: value for key, value in topics.items()
        if key in topic_keys
    }
    for key in topic_keys:
        if key in selected:
            continue
        normalized = str(key).replace("_", " ").replace("-", " ").strip()
        selected[key] = {
            "label": normalized.title() if normalized else str(key),
            "keywords": [normalized or str(key)],
        }
    return selected


def _capture_settings() -> tuple[str, int]:
    capture_settings = get_paper_distill_settings().get("capture", {})
    appendix_policy = str(capture_settings.get("appendix_policy", "summary_only"))
    min_body_chars = int(capture_settings.get("min_body_chars", 1500))
    return appendix_policy, min_body_chars


def _capture_options() -> dict[str, int | bool]:
    capture_settings = get_paper_distill_settings().get("capture", {})
    return {
        "preserve_math": bool(capture_settings.get("preserve_math", True)),
        "preserve_figures": bool(capture_settings.get("preserve_figures", True)),
        "preserve_tables": bool(capture_settings.get("preserve_tables", True)),
        "remove_refs": bool(capture_settings.get("remove_refs", True)),
        "remove_inline_citations": bool(capture_settings.get("remove_inline_citations", False)),
        "remove_internal_links": bool(capture_settings.get("remove_internal_links", True)),
        "write_structured_sidecar": bool(capture_settings.get("write_structured_sidecar", True)),
        "extract_figure_assets": bool(capture_settings.get("extract_figure_assets", False)),
        "max_figures": int(capture_settings.get("max_figures", 12)),
        "max_tables": int(capture_settings.get("max_tables", 12)),
        "max_equations": int(capture_settings.get("max_equations", 24)),
    }


def _capture_request_kwargs(
    appendix_policy: str,
    min_body_chars: int,
    capture_options: dict[str, int | bool] | None = None,
) -> dict[str, int | bool | str]:
    options = capture_options or {}
    return {
        "appendix_policy": appendix_policy,
        "min_body_chars": min_body_chars,
        "preserve_math": bool(options.get("preserve_math", True)),
        "preserve_figures": bool(options.get("preserve_figures", True)),
        "preserve_tables": bool(options.get("preserve_tables", True)),
        "max_figures": int(options.get("max_figures", 12)),
        "max_tables": int(options.get("max_tables", 12)),
        "max_equations": int(options.get("max_equations", 24)),
        "remove_refs": bool(options.get("remove_refs", True)),
        "remove_inline_citations": bool(options.get("remove_inline_citations", False)),
        "remove_internal_links": bool(options.get("remove_internal_links", True)),
    }


def _capture_method_from_source_doc(source_doc: object, fallback: str = "ar5iv_html_cleaned") -> str:
    capture_method = str(getattr(source_doc, "capture_method", "")).strip()
    return capture_method or fallback


def _relative_to_vault_if_possible(vault_path: str, maybe_path: str) -> str:
    if not maybe_path:
        return ""
    target = Path(maybe_path).expanduser()
    try:
        return str(target.relative_to(Path(vault_path).expanduser()))
    except ValueError:
        return str(target)


def _zotero_runtime(vault_path: str) -> dict[str, str]:
    zotero_settings = get_zotero_settings()
    mode = get_zotero_mode()
    enabled = bool(zotero_settings.get("enabled", True))
    if not enabled:
        mode = "disabled"

    return {
        "mode": mode,
        "collection_name": get_zotero_collection_name(),
        "library_id": get_env("ZOTERO_LIBRARY_ID"),
        "api_key": get_env("ZOTERO_API_KEY"),
        "local_export_dir": get_zotero_local_export_dir(vault_path),
    }
