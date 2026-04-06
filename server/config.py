"""Configuration helpers for Paper Distill."""
from __future__ import annotations

import json
import os
from functools import lru_cache
from pathlib import Path
from typing import Any


_REPO_ROOT = Path(__file__).resolve().parents[1]
_DEFAULT_SETTINGS_PATH = _REPO_ROOT / "settings.json"

_DEFAULT_PAPER_DISTILL_SETTINGS: dict[str, Any] = {
    "vault_path": "",
    "topics": {},
    "search": {
        "sources": ["arxiv", "s2", "openalex", "dblp", "pwc"],
        "max_per_topic": 20,
        "max_daily": 10,
    },
    "compile": {
        "auto_after_ingest": False,
        "deep_compile_threshold": 5,
        "source_policy": "notes_first",
    },
    "workflow": {
        "detailed_inbox_cards": True,
        "max_candidates_per_topic": 5,
        "diversity_cap_per_cluster": 2,
        "require_arxiv_binding": True,
    },
    "capture": {
        "cleaning_scope": "body_abstract_sections_captions",
        "appendix_policy": "summary_only",
        "failure_policy": "return_to_inbox",
        "min_body_chars": 1500,
        "preserve_math": True,
        "preserve_figures": True,
        "preserve_tables": True,
        "remove_refs": True,
        "remove_inline_citations": False,
        "remove_internal_links": True,
        "write_structured_sidecar": True,
        "extract_figure_assets": False,
        "max_figures": 12,
        "max_tables": 12,
        "max_equations": 24,
    },
    "venue": {
        "authority_order": ["dblp", "crossref", "openalex", "arxiv"],
    },
    "zotero": {
        "enabled": True,
        "mode": "local_first",
        "auto_collect": False,
        "collection_name": "Paper Distill v2",
        "local_export_dir": "Paper Distill/zotero/imports",
        "local_export_format": "csl_json",
    },
    "scoring": {
        "weights": {
            "topic_fit": 0.40,
            "recency": 0.20,
            "novelty": 0.15,
            "impact": 0.10,
            "venue_tier": 0.07,
            "author_preference": 0.05,
            "metadata_quality": 0.03,
        },
        "venue_aliases": {
            "nips": "NeurIPS",
            "neurips": "NeurIPS",
            "conference on robot learning": "CoRL",
        },
        "venue_tiers": {
            "tier_s": [
                "CVPR",
                "ICCV",
                "ECCV",
                "NeurIPS",
                "ICML",
                "ICLR",
                "AAAI",
                "ICRA",
                "IROS",
                "RSS",
                "CoRL",
            ],
            "tier_a": [],
        },
    },
    "research_profile": {
        "direction": "",
        "whitelist_authors": [],
        "seed_papers": [],
        "learned_preferences": {
            "accepted_keywords": [],
            "rejected_keywords": [],
            "preferred_venues": [],
            "feedback_count": 0,
        },
    },
}


def get_env(key: str, default: str = "") -> str:
    return os.environ.get(key, default)


def _deep_merge(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    merged = dict(base)
    for key, value in override.items():
        if isinstance(value, dict) and isinstance(merged.get(key), dict):
            merged[key] = _deep_merge(merged[key], value)
        else:
            merged[key] = value
    return merged


def _settings_path() -> Path:
    raw = get_env("SETTINGS_PATH", "").strip()
    if raw:
        return Path(raw).expanduser()
    return _DEFAULT_SETTINGS_PATH


@lru_cache(maxsize=1)
def load_settings() -> dict[str, Any]:
    path = _settings_path()
    if not path.exists():
        return {"paper_distill": dict(_DEFAULT_PAPER_DISTILL_SETTINGS)}

    try:
        with path.open("r", encoding="utf-8") as handle:
            parsed = json.load(handle)
    except (OSError, json.JSONDecodeError):
        return {"paper_distill": dict(_DEFAULT_PAPER_DISTILL_SETTINGS)}

    paper_distill = parsed.get("paper_distill", {})
    if not isinstance(paper_distill, dict):
        paper_distill = {}

    merged = _deep_merge(_DEFAULT_PAPER_DISTILL_SETTINGS, paper_distill)
    return {"paper_distill": merged}


def get_paper_distill_settings() -> dict[str, Any]:
    return load_settings().get("paper_distill", {})


def get_vault_path() -> str:
    env_path = get_env("VAULT_PATH", "").strip()
    if env_path:
        return env_path
    return str(get_paper_distill_settings().get("vault_path", "")).strip()


def get_topics() -> dict[str, Any]:
    topics = get_paper_distill_settings().get("topics", {})
    return topics if isinstance(topics, dict) else {}


def get_scoring_settings() -> dict[str, Any]:
    scoring = get_paper_distill_settings().get("scoring", {})
    return scoring if isinstance(scoring, dict) else {}


def get_zotero_settings() -> dict[str, Any]:
    zotero = get_paper_distill_settings().get("zotero", {})
    return zotero if isinstance(zotero, dict) else {}


def _normalize_mode(raw: str) -> str:
    mode = raw.strip().lower().replace("-", "_")
    if mode in {"local", "localfirst"}:
        return "local_first"
    if mode in {"cloud", "web", "webapi"}:
        return "web_api"
    if mode in {"off", "none"}:
        return "disabled"
    return mode or "local_first"


def get_zotero_mode() -> str:
    env_mode = get_env("ZOTERO_MODE", "").strip()
    if env_mode:
        return _normalize_mode(env_mode)
    return _normalize_mode(str(get_zotero_settings().get("mode", "local_first")))


def get_zotero_collection_name() -> str:
    env_name = get_env("ZOTERO_COLLECTION_NAME", "").strip()
    if env_name:
        return env_name
    return str(get_zotero_settings().get("collection_name", "Paper Distill v2")).strip()


def get_zotero_local_export_dir(vault_path: str | None = None) -> str:
    raw = (
        get_env("ZOTERO_LOCAL_EXPORT_DIR", "").strip()
        or str(get_zotero_settings().get("local_export_dir", "")).strip()
    )
    if not raw:
        raw = "Paper Distill/zotero/imports"

    export_path = Path(raw).expanduser()
    if export_path.is_absolute() or not vault_path:
        return str(export_path)
    return str((Path(vault_path).expanduser() / export_path).resolve())
