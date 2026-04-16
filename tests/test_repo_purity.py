from __future__ import annotations

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
LIVE_V3_MODULES = [
    "server/v3_alias.py",
    "server/v3_discovery.py",
    "server/v3_health.py",
    "server/v3_ingest.py",
    "server/v3_store.py",
    "server/tools_core.py",
    "server/tools_intake.py",
    "server/tools_knowledge.py",
    "server/tools_health.py",
]
FORBIDDEN_IMPORTS = [
    "server_runtime",
    "concept_registry",
    "vault_ops",
    "vault_query",
    "vault_lint",
]


def test_live_v3_modules_do_not_import_legacy_runtime() -> None:
    offenders: list[str] = []
    for rel in LIVE_V3_MODULES:
        source = (REPO_ROOT / rel).read_text(encoding="utf-8")
        for forbidden in FORBIDDEN_IMPORTS:
            if forbidden in source:
                offenders.append(f"{rel}: {forbidden}")
    assert offenders == []
