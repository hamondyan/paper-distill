from __future__ import annotations

from pathlib import Path


def test_maintenance_module_avoids_manual_visible_asset_writes() -> None:
    repo_root = Path(__file__).resolve().parents[1]
    maintenance_source = (repo_root / "server" / "maintenance.py").read_text(encoding="utf-8")

    assert 'with open(path, "w", encoding="utf-8") as f:' not in maintenance_source
    assert 'with open(topic_path, "w", encoding="utf-8") as f:' not in maintenance_source
    assert 'with open(concept_path, "w", encoding="utf-8") as f:' not in maintenance_source
    assert "def _render_markdown(" not in maintenance_source
