from __future__ import annotations

from pathlib import Path
from unittest.mock import Mock

import pytest

from server import qmd_runtime


def test_ensure_qmd_ready_bootstraps_missing_collections_and_contexts_idempotently(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    calls: list[list[str]] = []
    show_counts = {name: 0 for name in qmd_runtime.COLLECTIONS}
    contexts = {
        "qmd://canon-papers",
        "qmd://insights-conversations",
        "qmd://insights-ideas",
        "qmd://raw-evidence",
    }
    expected_alias = str((tmp_path / "wiki" / "papers").resolve()).replace("/private/var/", "/var/")

    def fake_run(args, **kwargs):
        calls.append(args)
        if args == ["qmd", "context", "list"]:
            return Mock(stdout="".join(f"{name}\n" for name in sorted(contexts)))
        if args[:2] == ["qmd", "collection"] and args[2] == "show":
            name = args[3]
            show_counts[name] += 1
            if name == "canon-papers" and show_counts[name] == 1:
                return Mock(
                    stdout=(
                        "Collection: canon-papers\n"
                        "  Path:     /elsewhere/vault/wiki/papers\n"
                        "  Pattern:  **/*.md\n"
                    )
                )
            if name == "canon-papers":
                return Mock(
                    stdout=(
                        f"Collection: canon-papers\n"
                        f"  Path:     {expected_alias}\n"
                        "  Pattern:  **/*.md\n"
                    )
                )
            rel = qmd_runtime.COLLECTIONS[name][0]
            return Mock(
                stdout=(
                    f"Collection: {name}\n"
                    f"  Path:     {(tmp_path / rel).resolve()}\n"
                    "  Pattern:  **/*.md\n"
                )
            )
        if args == ["qmd", "collection", "remove", "canon-papers"]:
            return Mock(stdout="")
        if args == ["qmd", "collection", "add", str(tmp_path / "wiki/papers"), "--name", "canon-papers"]:
            return Mock(stdout="")
        if args[:2] == ["qmd", "context"] and args[2] == "add":
            contexts.add(args[3])
            return Mock(stdout="")
        return Mock(stdout="")

    monkeypatch.setattr(qmd_runtime.subprocess, "run", fake_run)

    first = qmd_runtime.ensure_qmd_ready(tmp_path)
    second = qmd_runtime.ensure_qmd_ready(tmp_path)

    assert first == {"ready": True, "collections": list(qmd_runtime.COLLECTIONS.keys())}
    assert second == {"ready": True, "collections": list(qmd_runtime.COLLECTIONS.keys())}
    assert calls.count(
        ["qmd", "context", "add", "qmd://canon-concepts", "Canonical concept pages"]
    ) == 1
    assert calls.count(["qmd", "collection", "remove", "canon-papers"]) == 1
    assert calls.count(
        ["qmd", "collection", "add", str(tmp_path / "wiki/papers"), "--name", "canon-papers"]
    ) == 1
    assert calls.count(["qmd", "context", "list"]) == 3
    assert calls.count(["qmd", "collection", "show", "canon-papers"]) == 2


def test_ensure_qmd_ready_reconciles_wrong_collection_path(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    calls: list[list[str]] = []

    def fake_run(args, **kwargs):
        calls.append(args)
        if args == ["qmd", "collection", "list"]:
            return Mock(stdout="canon-papers\ncanon-concepts\ninsights-conversations\ninsights-ideas\nraw-evidence\n")
        if args == ["qmd", "context", "list"]:
            return Mock(stdout="qmd://canon-papers\nqmd://canon-concepts\nqmd://insights-conversations\nqmd://insights-ideas\nqmd://raw-evidence\n")
        if args == ["qmd", "collection", "show", "canon-papers"]:
            return Mock(
                stdout=(
                    "Collection: canon-papers\n"
                    "  Path:     /elsewhere/vault/wiki/papers\n"
                    "  Pattern:  **/*.md\n"
                )
            )
        if args == ["qmd", "collection", "remove", "canon-papers"]:
            return Mock(stdout="")
        if args == ["qmd", "collection", "add", str(tmp_path / "wiki/papers"), "--name", "canon-papers"]:
            return Mock(stdout="")
        if args[:2] == ["qmd", "collection"] and args[2] == "show":
            return Mock(
                stdout=(
                    f"Collection: {args[3]}\n"
                    f"  Path:     {tmp_path / 'wiki/concepts' if args[3] == 'canon-concepts' else tmp_path / 'insights/conversations' if args[3] == 'insights-conversations' else tmp_path / 'insights/ideas' if args[3] == 'insights-ideas' else tmp_path / 'raw/evidence'}\n"
                    "  Pattern:  **/*.md\n"
                )
            )
        return Mock(stdout="")

    monkeypatch.setattr(qmd_runtime.subprocess, "run", fake_run)

    result = qmd_runtime.ensure_qmd_ready(tmp_path)

    assert result == {"ready": True, "collections": list(qmd_runtime.COLLECTIONS.keys())}
    assert calls.count(["qmd", "collection", "show", "canon-papers"]) == 1
    assert ["qmd", "collection", "remove", "canon-papers"] in calls
    assert ["qmd", "collection", "add", str(tmp_path / "wiki/papers"), "--name", "canon-papers"] in calls
    assert ["qmd", "collection", "show", "canon-papers"] in calls


def test_ensure_qmd_ready_refreshes_contexts_after_remount(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    calls: list[list[str]] = []
    context_state = {"qmd://canon-papers"}

    def fake_run(args, **kwargs):
        calls.append(args)
        if args == ["qmd", "context", "list"]:
            return Mock(stdout="".join(f"{name}\n" for name in sorted(context_state)))
        if args == ["qmd", "collection", "list"]:
            return Mock(stdout="canon-papers\ncanon-concepts\ninsights-conversations\ninsights-ideas\nraw-evidence\n")
        if args == ["qmd", "collection", "show", "canon-papers"]:
            return Mock(
                stdout=(
                    "Collection: canon-papers\n"
                    "  Path:     /elsewhere/vault/wiki/papers\n"
                    "  Pattern:  **/*.md\n"
                )
            )
        if args == ["qmd", "collection", "remove", "canon-papers"]:
            context_state.discard("qmd://canon-papers")
            return Mock(stdout="")
        if args == ["qmd", "collection", "add", str(tmp_path / "wiki/papers"), "--name", "canon-papers"]:
            return Mock(stdout="")
        if args == ["qmd", "context", "add", "qmd://canon-papers", "Canonical distilled papers"]:
            context_state.add("qmd://canon-papers")
            return Mock(stdout="")
        if args[:2] == ["qmd", "collection"] and args[2] == "show":
            rel = qmd_runtime.COLLECTIONS[args[3]][0]
            return Mock(
                stdout=(
                    f"Collection: {args[3]}\n"
                    f"  Path:     {(tmp_path / rel).resolve()}\n"
                    "  Pattern:  **/*.md\n"
                )
            )
        return Mock(stdout="")

    monkeypatch.setattr(qmd_runtime.subprocess, "run", fake_run)

    result = qmd_runtime.ensure_qmd_ready(tmp_path)

    assert result == {"ready": True, "collections": list(qmd_runtime.COLLECTIONS.keys())}
    assert calls.count(["qmd", "collection", "remove", "canon-papers"]) == 1
    assert calls.count(["qmd", "context", "add", "qmd://canon-papers", "Canonical distilled papers"]) == 1


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


def test_qmd_ready_report_returns_ready_when_collections_match(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    def fake_run(args, **kwargs):
        if args == ["qmd", "collection", "list"]:
            return Mock(stdout="canon-papers\ncanon-concepts\ninsights-conversations\ninsights-ideas\nraw-evidence\n")
        if args[:2] == ["qmd", "collection"] and args[2] == "show":
            rel_path = qmd_runtime.COLLECTIONS[args[3]][0]
            return Mock(
                stdout=(
                    f"Collection: {args[3]}\n"
                    f"  Path:     {(tmp_path / rel_path).resolve()}\n"
                    "  Pattern:  **/*.md\n"
                )
            )
        raise AssertionError(args)

    monkeypatch.setattr(qmd_runtime.subprocess, "run", fake_run)

    assert qmd_runtime.qmd_ready_report(tmp_path) == {
        "status": "ready",
        "reason": "qmd collections available",
    }


def test_qmd_ready_report_returns_degraded_when_collection_is_missing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    def fake_run(args, **kwargs):
        if args == ["qmd", "collection", "list"]:
            return Mock(stdout="canon-papers\ncanon-concepts\ninsights-conversations\ninsights-ideas\nraw-evidence\n")
        if args == ["qmd", "collection", "show", "canon-papers"]:
            return Mock(
                stdout=(
                    "Collection: canon-papers\n"
                    "  Path:     /elsewhere/vault/wiki/papers\n"
                    "  Pattern:  **/*.md\n"
                )
            )
        if args[:2] == ["qmd", "collection"] and args[2] == "show":
            rel_path = qmd_runtime.COLLECTIONS[args[3]][0]
            return Mock(
                stdout=(
                    f"Collection: {args[3]}\n"
                    f"  Path:     {(tmp_path / rel_path).resolve()}\n"
                    "  Pattern:  **/*.md\n"
                )
            )
        raise AssertionError(args)

    monkeypatch.setattr(qmd_runtime.subprocess, "run", fake_run)

    assert qmd_runtime.qmd_ready_report(tmp_path) == {
        "status": "degraded",
        "reason": "missing qmd collections",
        "missing": ["canon-papers"],
    }


def test_qmd_runtime_only_exposes_bootstrap_helpers() -> None:
    for name in ("qmd_search", "qmd_get", "qmd_update", "qmd_reembed_force"):
        assert not hasattr(qmd_runtime, name), name
