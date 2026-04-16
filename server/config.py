"""Configuration helpers for Paper Distill."""
from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any


_REPO_ROOT = Path(__file__).resolve().parents[1]
_DEFAULT_SETTINGS_PATH = _REPO_ROOT / "settings.json"
_SCORING_WEIGHT_KEYS = (
    "topic_fit",
    "recency",
    "novelty",
    "impact",
    "venue_tier",
    "author_preference",
    "metadata_quality",
    "profile_alignment",
    "taste_alignment",
)


class ConfigError(RuntimeError):
    """Raised when settings.json is missing or invalid."""


def _settings_path() -> Path:
    return _DEFAULT_SETTINGS_PATH


def _missing(path: str) -> None:
    raise ConfigError(f"Missing required setting: {path}")


def _invalid(path: str, expected: str) -> None:
    raise ConfigError(f"Invalid configuration at {path}: expected {expected}")


def _require_mapping(value: Any, path: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        _invalid(path, "object")
    return value


def _require_string(value: Any, path: str, *, allow_empty: bool = False) -> str:
    if not isinstance(value, str):
        _invalid(path, "string")
    normalized = value.strip()
    if not allow_empty and not normalized:
        _invalid(path, "non-empty string")
    return normalized if not allow_empty else value


def _require_bool(value: Any, path: str) -> bool:
    if not isinstance(value, bool):
        _invalid(path, "boolean")
    return value


def _require_int(value: Any, path: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        _invalid(path, "integer")
    return value


def _require_number(value: Any, path: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        _invalid(path, "number")
    return float(value)


def _require_list(value: Any, path: str) -> list[Any]:
    if not isinstance(value, list):
        _invalid(path, "array")
    return value


def _require_key(mapping: dict[str, Any], key: str, parent_path: str) -> Any:
    path = f"{parent_path}.{key}"
    if key not in mapping:
        _missing(path)
    return mapping[key]


def _validate_string_list(value: Any, path: str, *, allow_empty: bool = False) -> list[str]:
    values = _require_list(value, path)
    return [
        _require_string(item, f"{path}[{index}]", allow_empty=allow_empty)
        for index, item in enumerate(values)
    ]


def _validate_string_mapping(value: Any, path: str) -> dict[str, str]:
    mapping = _require_mapping(value, path)
    return {
        str(key): _require_string(item, f"{path}.{key}")
        for key, item in mapping.items()
    }


def _validate_string_list_mapping(value: Any, path: str) -> dict[str, list[str]]:
    mapping = _require_mapping(value, path)
    return {
        str(key): _validate_string_list(item, f"{path}.{key}")
        for key, item in mapping.items()
    }


def _validate_topics(value: Any, path: str) -> dict[str, dict[str, Any]]:
    topics = _require_mapping(value, path)
    validated: dict[str, dict[str, Any]] = {}
    for topic_name, topic_payload in topics.items():
        topic_path = f"{path}.{topic_name}"
        topic = _require_mapping(topic_payload, topic_path)
        validated[str(topic_name)] = {
            "label": _require_string(_require_key(topic, "label", topic_path), f"{topic_path}.label"),
            "keywords": _validate_string_list(
                _require_key(topic, "keywords", topic_path),
                f"{topic_path}.keywords",
            ),
            "weight": _require_number(
                _require_key(topic, "weight", topic_path),
                f"{topic_path}.weight",
            ),
        }
    return validated


def _validate_paper_distill_settings(value: Any) -> dict[str, Any]:
    paper_distill = _require_mapping(value, "paper_distill")

    qmd_settings = _require_mapping(
        _require_key(paper_distill, "qmd", "paper_distill"),
        "paper_distill.qmd",
    )
    search_settings = _require_mapping(
        _require_key(paper_distill, "search", "paper_distill"),
        "paper_distill.search",
    )
    workflow_settings = _require_mapping(
        _require_key(paper_distill, "workflow", "paper_distill"),
        "paper_distill.workflow",
    )
    capture_settings = _require_mapping(
        _require_key(paper_distill, "capture", "paper_distill"),
        "paper_distill.capture",
    )
    venue_settings = _require_mapping(
        _require_key(paper_distill, "venue", "paper_distill"),
        "paper_distill.venue",
    )
    scoring_settings = _require_mapping(
        _require_key(paper_distill, "scoring", "paper_distill"),
        "paper_distill.scoring",
    )
    scoring_weights = _require_mapping(
        _require_key(scoring_settings, "weights", "paper_distill.scoring"),
        "paper_distill.scoring.weights",
    )
    research_profile = _require_mapping(
        _require_key(paper_distill, "research_profile", "paper_distill"),
        "paper_distill.research_profile",
    )
    learned_preferences = _require_mapping(
        _require_key(research_profile, "learned_preferences", "paper_distill.research_profile"),
        "paper_distill.research_profile.learned_preferences",
    )

    validated_weights: dict[str, float] = {}
    for weight_key in _SCORING_WEIGHT_KEYS:
        validated_weights[weight_key] = _require_number(
            _require_key(scoring_weights, weight_key, "paper_distill.scoring.weights"),
            f"paper_distill.scoring.weights.{weight_key}",
        )

    return {
        "vault_path": _require_string(
            _require_key(paper_distill, "vault_path", "paper_distill"),
            "paper_distill.vault_path",
        ),
        "qmd": {
            "binary": _require_string(
                _require_key(qmd_settings, "binary", "paper_distill.qmd"),
                "paper_distill.qmd.binary",
            ),
        },
        "topics": _validate_topics(
            _require_key(paper_distill, "topics", "paper_distill"),
            "paper_distill.topics",
        ),
        "search": {
            "sources": _validate_string_list(
                _require_key(search_settings, "sources", "paper_distill.search"),
                "paper_distill.search.sources",
            ),
            "max_per_topic": _require_int(
                _require_key(search_settings, "max_per_topic", "paper_distill.search"),
                "paper_distill.search.max_per_topic",
            ),
            "max_daily": _require_int(
                _require_key(search_settings, "max_daily", "paper_distill.search"),
                "paper_distill.search.max_daily",
            ),
            "contact_email": _require_string(
                _require_key(search_settings, "contact_email", "paper_distill.search"),
                "paper_distill.search.contact_email",
                allow_empty=True,
            ),
            "unpaywall_email": _require_string(
                _require_key(search_settings, "unpaywall_email", "paper_distill.search"),
                "paper_distill.search.unpaywall_email",
                allow_empty=True,
            ),
            "semantic_scholar_api_key": _require_string(
                _require_key(
                    search_settings,
                    "semantic_scholar_api_key",
                    "paper_distill.search",
                ),
                "paper_distill.search.semantic_scholar_api_key",
                allow_empty=True,
            ),
        },
        "workflow": {
            "detailed_inbox_cards": _require_bool(
                _require_key(workflow_settings, "detailed_inbox_cards", "paper_distill.workflow"),
                "paper_distill.workflow.detailed_inbox_cards",
            ),
            "max_candidates_per_topic": _require_int(
                _require_key(workflow_settings, "max_candidates_per_topic", "paper_distill.workflow"),
                "paper_distill.workflow.max_candidates_per_topic",
            ),
            "diversity_cap_per_cluster": _require_int(
                _require_key(workflow_settings, "diversity_cap_per_cluster", "paper_distill.workflow"),
                "paper_distill.workflow.diversity_cap_per_cluster",
            ),
            "require_arxiv_binding": _require_bool(
                _require_key(workflow_settings, "require_arxiv_binding", "paper_distill.workflow"),
                "paper_distill.workflow.require_arxiv_binding",
            ),
        },
        "capture": {
            "cleaning_scope": _require_string(
                _require_key(capture_settings, "cleaning_scope", "paper_distill.capture"),
                "paper_distill.capture.cleaning_scope",
            ),
            "appendix_policy": _require_string(
                _require_key(capture_settings, "appendix_policy", "paper_distill.capture"),
                "paper_distill.capture.appendix_policy",
            ),
            "failure_policy": _require_string(
                _require_key(capture_settings, "failure_policy", "paper_distill.capture"),
                "paper_distill.capture.failure_policy",
            ),
            "min_body_chars": _require_int(
                _require_key(capture_settings, "min_body_chars", "paper_distill.capture"),
                "paper_distill.capture.min_body_chars",
            ),
            "preserve_math": _require_bool(
                _require_key(capture_settings, "preserve_math", "paper_distill.capture"),
                "paper_distill.capture.preserve_math",
            ),
            "preserve_figures": _require_bool(
                _require_key(capture_settings, "preserve_figures", "paper_distill.capture"),
                "paper_distill.capture.preserve_figures",
            ),
            "preserve_tables": _require_bool(
                _require_key(capture_settings, "preserve_tables", "paper_distill.capture"),
                "paper_distill.capture.preserve_tables",
            ),
            "remove_refs": _require_bool(
                _require_key(capture_settings, "remove_refs", "paper_distill.capture"),
                "paper_distill.capture.remove_refs",
            ),
            "remove_inline_citations": _require_bool(
                _require_key(capture_settings, "remove_inline_citations", "paper_distill.capture"),
                "paper_distill.capture.remove_inline_citations",
            ),
            "remove_internal_links": _require_bool(
                _require_key(capture_settings, "remove_internal_links", "paper_distill.capture"),
                "paper_distill.capture.remove_internal_links",
            ),
            "write_structured_sidecar": _require_bool(
                _require_key(capture_settings, "write_structured_sidecar", "paper_distill.capture"),
                "paper_distill.capture.write_structured_sidecar",
            ),
            "extract_figure_assets": _require_bool(
                _require_key(capture_settings, "extract_figure_assets", "paper_distill.capture"),
                "paper_distill.capture.extract_figure_assets",
            ),
            "max_figures": _require_int(
                _require_key(capture_settings, "max_figures", "paper_distill.capture"),
                "paper_distill.capture.max_figures",
            ),
            "max_tables": _require_int(
                _require_key(capture_settings, "max_tables", "paper_distill.capture"),
                "paper_distill.capture.max_tables",
            ),
            "max_equations": _require_int(
                _require_key(capture_settings, "max_equations", "paper_distill.capture"),
                "paper_distill.capture.max_equations",
            ),
        },
        "venue": {
            "authority_order": _validate_string_list(
                _require_key(venue_settings, "authority_order", "paper_distill.venue"),
                "paper_distill.venue.authority_order",
            ),
        },
        "scoring": {
            "weights": validated_weights,
            "venue_aliases": _validate_string_mapping(
                _require_key(scoring_settings, "venue_aliases", "paper_distill.scoring"),
                "paper_distill.scoring.venue_aliases",
            ),
            "venue_tiers": _validate_string_list_mapping(
                _require_key(scoring_settings, "venue_tiers", "paper_distill.scoring"),
                "paper_distill.scoring.venue_tiers",
            ),
        },
        "research_profile": {
            "direction": _require_string(
                _require_key(research_profile, "direction", "paper_distill.research_profile"),
                "paper_distill.research_profile.direction",
                allow_empty=True,
            ),
            "whitelist_authors": _validate_string_list(
                _require_key(research_profile, "whitelist_authors", "paper_distill.research_profile"),
                "paper_distill.research_profile.whitelist_authors",
                allow_empty=True,
            ),
            "seed_papers": _validate_string_list(
                _require_key(research_profile, "seed_papers", "paper_distill.research_profile"),
                "paper_distill.research_profile.seed_papers",
                allow_empty=True,
            ),
            "learned_preferences": {
                "accepted_keywords": _validate_string_list(
                    _require_key(
                        learned_preferences,
                        "accepted_keywords",
                        "paper_distill.research_profile.learned_preferences",
                    ),
                    "paper_distill.research_profile.learned_preferences.accepted_keywords",
                    allow_empty=True,
                ),
                "rejected_keywords": _validate_string_list(
                    _require_key(
                        learned_preferences,
                        "rejected_keywords",
                        "paper_distill.research_profile.learned_preferences",
                    ),
                    "paper_distill.research_profile.learned_preferences.rejected_keywords",
                    allow_empty=True,
                ),
                "preferred_venues": _validate_string_list(
                    _require_key(
                        learned_preferences,
                        "preferred_venues",
                        "paper_distill.research_profile.learned_preferences",
                    ),
                    "paper_distill.research_profile.learned_preferences.preferred_venues",
                    allow_empty=True,
                ),
                "feedback_count": _require_int(
                    _require_key(
                        learned_preferences,
                        "feedback_count",
                        "paper_distill.research_profile.learned_preferences",
                    ),
                    "paper_distill.research_profile.learned_preferences.feedback_count",
                ),
            },
        },
    }


@lru_cache(maxsize=1)
def load_settings() -> dict[str, Any]:
    path = _settings_path()
    if not path.exists():
        raise ConfigError(f"settings.json not found at {path}")

    try:
        with path.open("r", encoding="utf-8") as handle:
            parsed = json.load(handle)
    except OSError as exc:
        raise ConfigError(f"Could not read settings.json at {path}: {exc}") from exc
    except json.JSONDecodeError as exc:
        raise ConfigError(
            f"Invalid settings.json at {path}: line {exc.lineno} column {exc.colno}: {exc.msg}"
        ) from exc

    if not isinstance(parsed, dict):
        raise ConfigError("Invalid configuration at root: expected object")

    if "paper_distill" not in parsed:
        _missing("paper_distill")

    return {"paper_distill": _validate_paper_distill_settings(parsed["paper_distill"])}


def get_paper_distill_settings() -> dict[str, Any]:
    return load_settings()["paper_distill"]


def get_vault_path() -> str:
    return get_paper_distill_settings()["vault_path"]


def get_topics() -> dict[str, Any]:
    return get_paper_distill_settings()["topics"]


def get_search_settings() -> dict[str, Any]:
    return get_paper_distill_settings()["search"]


def get_scoring_settings() -> dict[str, Any]:
    return get_paper_distill_settings()["scoring"]


def get_qmd_binary() -> str:
    return get_paper_distill_settings()["qmd"]["binary"]
