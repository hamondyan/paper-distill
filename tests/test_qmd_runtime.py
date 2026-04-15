from __future__ import annotations

from pathlib import Path
from unittest.mock import Mock

import pytest

from server import qmd_runtime


def test_ensure_qmd_ready_bootstraps_missing_collections_and_contexts_idempotently(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    calls: list[list[str]] = []
    lists = iter(
        [
            "canon-papers\ninsights-conversations\n",
            "qmd://canon-papers\n",
            "canon-papers\ncanon-concepts\ninsights-conversations\ninsights-ideas\nraw-evidence\n",
            "qmd://canon-papers\nqmd://canon-concepts\nqmd://insights-conversations\nqmd://insights-ideas\nqmd://raw-evidence\n",
        ]
    )

    def fake_run(args, **kwargs):
        calls.append(args)
        if args[:2] == ["qmd", "collection"] and args[2] == "list":
            return Mock(stdout=next(lists))
        if args[:2] == ["qmd", "context"] and args[2] == "list":
            return Mock(stdout=next(lists))
        return Mock(stdout="")

    monkeypatch.setattr(qmd_runtime.subprocess, "run", fake_run)

    first = qmd_runtime.ensure_qmd_ready(tmp_path)
    second = qmd_runtime.ensure_qmd_ready(tmp_path)

    assert first == {"ready": True, "collections": list(qmd_runtime.COLLECTIONS.keys())}
    assert second == {"ready": True, "collections": list(qmd_runtime.COLLECTIONS.keys())}
    assert calls.count(
        ["qmd", "collection", "add", str(tmp_path / "wiki/concepts"), "--name", "canon-concepts"]
    ) == 1
    assert calls.count(
        ["qmd", "context", "add", "qmd://canon-concepts", "Canonical concept pages"]
    ) == 1
    assert calls.count(["qmd", "collection", "list"]) == 2
    assert calls.count(["qmd", "context", "list"]) == 2


def test_qmd_ready_report_returns_not_ready_when_binary_missing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    def fake_run(*_args, **_kwargs):
        raise FileNotFoundError

    monkeypatch.setattr(qmd_runtime.subprocess, "run", fake_run)

    assert qmd_runtime.qmd_ready_report(tmp_path) == {
        "status": "not_ready",
        "reason": "qmd binary not found",
    }


def test_qmd_search_constructs_query_for_scope(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    recorded: dict[str, list[str]] = {}

    def fake_ready(_vault_path: Path) -> dict[str, str]:
        return {"status": "ready"}

    def fake_run(args, **kwargs):
        recorded["args"] = args
        return Mock(stdout="[]")

    monkeypatch.setattr(qmd_runtime, "qmd_ready_report", fake_ready)
    monkeypatch.setattr(qmd_runtime.subprocess, "run", fake_run)

    result = qmd_runtime.qmd_search(tmp_path, "graph attention", "canon")

    assert result["status"] == "ok"
    assert recorded["args"] == [
        "qmd",
        "query",
        "graph attention",
        "--json",
        "-c",
        "canon-papers",
        "-c",
        "canon-concepts",
    ]


def test_qmd_get_constructs_command_for_existing_path(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    doc = tmp_path / "wiki" / "papers" / "paper.md"
    doc.parent.mkdir(parents=True)
    doc.write_text("# paper\n", encoding="utf-8")

    recorded: dict[str, list[str]] = {}

    def fake_run(args, **kwargs):
        recorded["args"] = args
        return Mock(stdout="body text")

    monkeypatch.setattr(qmd_runtime.subprocess, "run", fake_run)

    result = qmd_runtime.qmd_get(tmp_path, str(doc))

    assert result == {"status": "ok", "path": str(doc), "body": "body text"}
    assert recorded["args"] == ["qmd", "get", str(doc)]


def test_qmd_update_wraps_success_and_error(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    def fake_run(args, **kwargs):
        if args == ["qmd", "update"]:
            return Mock(stdout="updated")
        raise AssertionError(args)

    monkeypatch.setattr(qmd_runtime.subprocess, "run", fake_run)
    assert qmd_runtime.qmd_update(tmp_path) == {"ok": True, "stdout": "updated"}

    def failing_run(args, **kwargs):
        raise qmd_runtime.subprocess.CalledProcessError(1, args, stderr="boom")

    monkeypatch.setattr(qmd_runtime.subprocess, "run", failing_run)
    assert qmd_runtime.qmd_update(tmp_path) == {"ok": False, "error": "boom"}


def test_qmd_reembed_force_wraps_success_and_error(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    def fake_run(args, **kwargs):
        if args == ["qmd", "embed", "-f"]:
            return Mock(stdout="embedded")
        raise AssertionError(args)

    monkeypatch.setattr(qmd_runtime.subprocess, "run", fake_run)
    assert qmd_runtime.qmd_reembed_force(tmp_path) == {"ok": True, "stdout": "embedded"}

    def failing_run(args, **kwargs):
        raise qmd_runtime.subprocess.CalledProcessError(1, args, stderr="embed failed")

    monkeypatch.setattr(qmd_runtime.subprocess, "run", failing_run)
    assert qmd_runtime.qmd_reembed_force(tmp_path) == {"ok": False, "error": "embed failed"}
