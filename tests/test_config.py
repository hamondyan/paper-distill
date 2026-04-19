from __future__ import annotations

import json
from pathlib import Path

import pytest

from server import config


@pytest.fixture(autouse=True)
def _clear_config_cache_between_tests() -> None:
    config.load_settings.cache_clear()
    yield
    config.load_settings.cache_clear()


def _set_settings_path(monkeypatch: pytest.MonkeyPatch, path: Path) -> None:
    monkeypatch.setattr(config, "_DEFAULT_SETTINGS_PATH", path)
    config.load_settings.cache_clear()


def _config_error_type() -> type[BaseException]:
    return getattr(config, "ConfigError", RuntimeError)


def _write_settings(path: Path, payload: dict) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _valid_settings(vault_path: str = "/vault/from/settings") -> dict:
    return {
        "paper_distill": {
            "vault_path": vault_path,
            "qmd": {"binary": "qmd-from-settings"},
            "topics": {
                "robotics": {
                    "label": "Robotics",
                    "keywords": ["robotics", "manipulation"],
                    "weight": 1.0,
                }
            },
            "search": {
                "sources": ["arxiv", "s2", "openalex", "dblp", "pwc"],
                "max_per_topic": 20,
                "max_daily": 10,
                "contact_email": "contact@example.com",
                "unpaywall_email": "oa@example.com",
                "semantic_scholar_api_key": "s2-key-from-settings",
            },
            "workflow": {
                "max_candidates_per_topic": 5,
                "diversity_cap_per_cluster": 2,
                "require_arxiv_binding": True,
            },
            "capture": {
                "cleaning_scope": "body_abstract_sections_captions",
                "appendix_policy": "summary_only",
                "failure_policy": "report_error",
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
            "scoring": {
                "weights": {
                    "topic_fit": 0.40,
                    "recency": 0.20,
                    "novelty": 0.15,
                    "impact": 0.10,
                    "venue_tier": 0.07,
                    "author_preference": 0.05,
                    "metadata_quality": 0.03,
                    "profile_alignment": 0.05,
                    "taste_alignment": 0.03,
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
                "direction": "Embodied AI for robot manipulation",
                "whitelist_authors": ["Sergey Levine"],
                "seed_papers": ["10.48550/arxiv.2410.24164"],
                "learned_preferences": {
                    "accepted_keywords": [],
                    "rejected_keywords": [],
                    "preferred_venues": [],
                    "feedback_count": 0,
                },
            },
        }
    }


def test_load_settings_ignores_environment_overrides_and_reads_settings_json(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    settings_path = tmp_path / "settings.json"
    _write_settings(settings_path, _valid_settings(vault_path="/repo/settings/vault"))
    _set_settings_path(monkeypatch, settings_path)
    monkeypatch.setenv("SETTINGS_PATH", str(tmp_path / "other-settings.json"))
    monkeypatch.setenv("VAULT_PATH", "/env/vault")
    monkeypatch.setenv("PAPER_DISTILL_QMD_BINARY", "env-qmd")
    monkeypatch.setenv("OPENALEX_EMAIL", "env-openalex@example.com")
    monkeypatch.setenv("UNPAYWALL_EMAIL", "env-unpaywall@example.com")
    monkeypatch.setenv("S2_API_KEY", "env-s2-key")

    assert config.get_vault_path() == "/repo/settings/vault"
    assert config.get_qmd_binary() == "qmd-from-settings"
    assert config.get_search_settings()["contact_email"] == "contact@example.com"
    assert config.get_search_settings()["unpaywall_email"] == "oa@example.com"
    assert config.get_search_settings()["semantic_scholar_api_key"] == "s2-key-from-settings"


def test_load_settings_raises_config_error_when_settings_file_is_missing(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _set_settings_path(monkeypatch, tmp_path / "missing-settings.json")

    with pytest.raises(_config_error_type(), match="settings.json"):
        config.load_settings()


def test_load_settings_raises_config_error_with_missing_field_path(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    settings_path = tmp_path / "settings.json"
    payload = _valid_settings()
    del payload["paper_distill"]["capture"]["max_figures"]
    _write_settings(settings_path, payload)
    _set_settings_path(monkeypatch, settings_path)

    with pytest.raises(_config_error_type(), match="paper_distill.capture.max_figures"):
        config.load_settings()


def test_load_settings_raises_config_error_with_missing_search_provider_field_path(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    settings_path = tmp_path / "settings.json"
    payload = _valid_settings()
    del payload["paper_distill"]["search"]["contact_email"]
    _write_settings(settings_path, payload)
    _set_settings_path(monkeypatch, settings_path)

    with pytest.raises(_config_error_type(), match="paper_distill.search.contact_email"):
        config.load_settings()


def test_load_settings_raises_config_error_with_invalid_field_type_path(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    settings_path = tmp_path / "settings.json"
    payload = _valid_settings()
    payload["paper_distill"]["search"]["max_daily"] = "10"
    _write_settings(settings_path, payload)
    _set_settings_path(monkeypatch, settings_path)

    with pytest.raises(_config_error_type(), match="paper_distill.search.max_daily"):
        config.load_settings()


def test_load_settings_returns_validated_settings_without_python_fallbacks(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    settings_path = tmp_path / "settings.json"
    payload = _valid_settings(vault_path="/validated/vault")
    _write_settings(settings_path, payload)
    _set_settings_path(monkeypatch, settings_path)

    settings = config.get_paper_distill_settings()

    assert settings["vault_path"] == "/validated/vault"
    assert settings["qmd"]["binary"] == "qmd-from-settings"
    assert settings["search"]["contact_email"] == "contact@example.com"
    assert "detailed_inbox_cards" not in settings["workflow"]
    assert settings["scoring"]["weights"]["profile_alignment"] == 0.05
