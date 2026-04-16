from __future__ import annotations

import subprocess
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
LEGACY_RUNTIME_FILES = [
    "server/active_threads.py",
    "server/capture_settings.py",
    "server/compile_ir.py",
    "server/concept_registry.py",
    "server/context_assembler.py",
    "server/crgp_tools.py",
    "server/database.py",
    "server/dialogue_capture.py",
    "server/discovery_helpers.py",
    "server/idea_verification.py",
    "server/ingestion_helpers.py",
    "server/maintenance.py",
    "server/memory_compile.py",
    "server/memory_consolidation.py",
    "server/memory_contract.py",
    "server/memory_promotion.py",
    "server/memory_runtime.py",
    "server/obsidian_query.py",
    "server/paper_frontmatter.py",
    "server/paper_identity.py",
    "server/research_item.py",
    "server/server_runtime.py",
    "server/template_render.py",
    "server/tools_ideas.py",
    "server/vault_contract.py",
    "server/vault_lint.py",
    "server/vault_ops.py",
    "server/vault_query.py",
    "server/zotero/__init__.py",
    "server/zotero/client.py",
]
LEGACY_TEST_FILES = [
    "tests/test_asset_writers.py",
    "tests/test_compile_ir.py",
    "tests/test_compile_patch_engine.py",
    "tests/test_context_assembler.py",
    "tests/test_crgp_unified.py",
    "tests/test_database_schema.py",
    "tests/test_dialogue_capture.py",
    "tests/test_idea_verification.py",
    "tests/test_maintenance_execution.py",
    "tests/test_memory_compile.py",
    "tests/test_memory_contract.py",
    "tests/test_memory_promotion.py",
    "tests/test_memory_runtime.py",
    "tests/test_obsidian_query.py",
    "tests/test_paper_add.py",
    "tests/test_productization.py",
    "tests/test_registry_maintenance.py",
    "tests/test_server_tools.py",
    "tests/test_template_inventory.py",
    "tests/test_trigger_candidates.py",
    "tests/test_vault_lint.py",
    "tests/test_vault_query.py",
    "tests/test_writer_boundaries.py",
    "tests/test_zotero_client.py",
]


def _tracked_paths() -> set[str]:
    result = subprocess.run(
        ["git", "ls-files"],
        cwd=REPO_ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    return {line.strip() for line in result.stdout.splitlines() if line.strip()}


def test_legacy_runtime_and_tests_are_no_longer_tracked() -> None:
    tracked = _tracked_paths()
    offenders = [path for path in LEGACY_RUNTIME_FILES + LEGACY_TEST_FILES if path in tracked]
    assert offenders == []


def test_tracked_cache_artifacts_are_removed() -> None:
    tracked = _tracked_paths()
    offenders = [path for path in tracked if "__pycache__" in path or path.endswith(".pyc")]
    assert offenders == []
