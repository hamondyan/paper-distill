from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path

import pytest

from server import cli


def test_admin_cli_rejects_retired_export_and_backfill_commands(
    capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(sys, "argv", ["paper-distill-admin", "export-db"])

    with pytest.raises(SystemExit) as excinfo:
        cli.main()

    assert excinfo.value.code == 2
    assert "invalid choice" in capsys.readouterr().err


def test_bootstrap_reports_clean_error_when_qmd_init_fails(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    def fake_layout(_vault_path: Path) -> dict[str, list[str]]:
        return {"created": ["inbox"]}

    def failing_qmd(_vault_path: Path) -> dict[str, object]:
        return {"status": "not_ready", "reason": "qmd binary not found"}

    monkeypatch.setattr(cli, "ensure_v3_layout", fake_layout)
    monkeypatch.setattr(cli, "ensure_qmd_ready", failing_qmd)

    with pytest.raises(SystemExit) as excinfo:
        asyncio.run(cli._bootstrap(type("Args", (), {"vault_path": str(tmp_path)})()))

    assert excinfo.value.code == 1
    stderr = capsys.readouterr().err.strip()
    payload = json.loads(stderr)
    assert payload == {
        "layout": {"created": ["inbox"]},
        "qmd": {"status": "not_ready", "reason": "qmd binary not found"},
    }


def test_bootstrap_reports_layout_and_qmd_payload_on_success(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    def fake_layout(_vault_path: Path) -> dict[str, list[str]]:
        return {"created": ["inbox", "wiki/papers"]}

    def ready_qmd(_vault_path: Path) -> dict[str, object]:
        return {"ready": True, "collections": ["canon-papers"]}

    monkeypatch.setattr(cli, "ensure_v3_layout", fake_layout)
    monkeypatch.setattr(cli, "ensure_qmd_ready", ready_qmd)

    asyncio.run(cli._bootstrap(type("Args", (), {"vault_path": str(tmp_path)})()))

    captured = capsys.readouterr()
    assert captured.err == ""
    assert json.loads(captured.out) == {
        "layout": {"created": ["inbox", "wiki/papers"]},
        "qmd": {"ready": True, "collections": ["canon-papers"]},
    }
