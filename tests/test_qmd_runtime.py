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


def test_qmd_search_blocks_when_readiness_is_degraded(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    def fake_ready(_vault_path: Path) -> dict[str, object]:
        return {"status": "degraded", "reason": "missing qmd collections"}

    def fail_run(*_args, **_kwargs):
        raise AssertionError("query should not run when readiness is degraded")

    monkeypatch.setattr(qmd_runtime, "qmd_ready_report", fake_ready)
    monkeypatch.setattr(qmd_runtime.subprocess, "run", fail_run)

    result = qmd_runtime.qmd_search(tmp_path, "graph attention", "canon")

    assert result == {"status": "degraded", "error": "missing qmd collections"}


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


def test_qmd_get_resolves_vault_relative_explicit_path(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    doc = tmp_path / "wiki" / "concepts" / "transformer.md"
    doc.parent.mkdir(parents=True)
    doc.write_text("# transformer\n", encoding="utf-8")

    recorded: dict[str, list[str]] = {}

    def fake_run(args, **kwargs):
        recorded["args"] = args
        return Mock(stdout="relative body")

    monkeypatch.setattr(qmd_runtime.subprocess, "run", fake_run)

    result = qmd_runtime.qmd_get(tmp_path, "wiki/concepts/transformer.md")

    assert result == {"status": "ok", "path": str(doc), "body": "relative body"}
    assert recorded["args"] == ["qmd", "get", str(doc)]


def test_qmd_get_rejects_explicit_path_escape_outside_vault(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    outside = tmp_path.parent / "outside.md"
    outside.write_text("# outside\n", encoding="utf-8")

    def fail_run(*_args, **_kwargs):
        raise AssertionError("qmd should not run for escaping paths")

    monkeypatch.setattr(qmd_runtime.subprocess, "run", fail_run)

    result = qmd_runtime.qmd_get(tmp_path, "../outside.md")

    assert result == {"status": "error", "error": "path escapes vault: ../outside.md"}


def test_qmd_get_resolves_stable_identifier_to_canonical_filename(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    doc = tmp_path / "wiki" / "papers" / "attention--arxiv-1706.03762.md"
    doc.parent.mkdir(parents=True)
    doc.write_text("# attention\n", encoding="utf-8")

    recorded: dict[str, list[str]] = {}

    def fake_run(args, **kwargs):
        recorded["args"] = args
        return Mock(stdout="resolved body")

    monkeypatch.setattr(qmd_runtime.subprocess, "run", fake_run)

    result = qmd_runtime.qmd_get(tmp_path, "arxiv:1706.03762")

    assert result == {"status": "ok", "path": str(doc), "body": "resolved body"}
    assert recorded["args"] == ["qmd", "get", str(doc)]


def test_qmd_get_prefers_canonical_paper_namespace_over_raw_evidence(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    canon_doc = tmp_path / "wiki" / "papers" / "paper--arxiv-1706.03762.md"
    raw_doc = tmp_path / "raw" / "evidence" / "paper--arxiv-1706.03762.md"
    canon_doc.parent.mkdir(parents=True)
    raw_doc.parent.mkdir(parents=True)
    canon_doc.write_text("# canon\n", encoding="utf-8")
    raw_doc.write_text("# raw\n", encoding="utf-8")

    recorded: dict[str, list[str]] = {}

    def fake_run(args, **kwargs):
        recorded["args"] = args
        return Mock(stdout="canon body")

    monkeypatch.setattr(qmd_runtime.subprocess, "run", fake_run)

    result = qmd_runtime.qmd_get(tmp_path, "arxiv:1706.03762")

    assert result == {"status": "ok", "path": str(canon_doc), "body": "canon body"}
    assert recorded["args"] == ["qmd", "get", str(canon_doc)]


def test_qmd_get_resolves_doi_style_identifier_to_canonical_filename(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    doc = tmp_path / "wiki" / "papers" / "paper--10.1000-xyz.md"
    doc.parent.mkdir(parents=True)
    doc.write_text("# paper\n", encoding="utf-8")

    recorded: dict[str, list[str]] = {}

    def fake_run(args, **kwargs):
        recorded["args"] = args
        return Mock(stdout="doi body")

    monkeypatch.setattr(qmd_runtime.subprocess, "run", fake_run)

    result = qmd_runtime.qmd_get(tmp_path, "10.1000/xyz")

    assert result == {"status": "ok", "path": str(doc), "body": "doi body"}
    assert recorded["args"] == ["qmd", "get", str(doc)]


def test_qmd_get_returns_not_ready_when_binary_missing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    doc = tmp_path / "wiki" / "papers" / "paper.md"
    doc.parent.mkdir(parents=True)
    doc.write_text("# paper\n", encoding="utf-8")

    def fake_run(*_args, **_kwargs):
        raise FileNotFoundError

    monkeypatch.setattr(qmd_runtime.subprocess, "run", fake_run)

    assert qmd_runtime.qmd_get(tmp_path, str(doc)) == {
        "status": "not_ready",
        "reason": "qmd binary not found",
    }


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


def test_qmd_update_returns_not_ready_when_binary_missing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    def fake_run(*_args, **_kwargs):
        raise FileNotFoundError

    monkeypatch.setattr(qmd_runtime.subprocess, "run", fake_run)

    assert qmd_runtime.qmd_update(tmp_path) == {"ok": False, "error": "qmd binary not found"}


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


def test_qmd_reembed_force_returns_not_ready_when_binary_missing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    def fake_run(*_args, **_kwargs):
        raise FileNotFoundError

    monkeypatch.setattr(qmd_runtime.subprocess, "run", fake_run)

    assert qmd_runtime.qmd_reembed_force(tmp_path) == {"ok": False, "error": "qmd binary not found"}
