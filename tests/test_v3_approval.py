from __future__ import annotations

import asyncio
from pathlib import Path

from server import tools_intake
from server.v3_approval import approve_papers_v3


def _write_inbox_note(
    path: Path,
    *,
    paper_id: str,
    title: str,
    source_url: str = "https://arxiv.org/abs/1706.03762",
    body: str = "Review this stub before ingesting.",
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        (
            "---\n"
            f'paper_id: "{paper_id}"\n'
            f'title: "{title}"\n'
            f'source_url: "{source_url}"\n'
            "---\n\n"
            f"# {title}\n\n"
            f"{body}\n"
        ),
        encoding="utf-8",
    )


def test_approve_papers_marks_matching_inbox_note_by_paper_id(tmp_path: Path) -> None:
    note_path = tmp_path / "inbox" / "attention.md"
    _write_inbox_note(
        note_path,
        paper_id="arxiv:1706.03762",
        title="Attention Is All You Need",
    )

    result = approve_papers_v3(tmp_path, "arxiv:1706.03762")

    text = note_path.read_text(encoding="utf-8")
    assert result["ok"] is True
    assert result["approved_count"] == 1
    assert result["already_approved_count"] == 0
    assert result["approved"][0]["paper_id"] == "arxiv:1706.03762"
    assert result["approved"][0]["path"] == str(note_path)
    assert text.endswith("\n#approved\n")
    assert result["follow_up"] == [
        "Run /ingest approved when you are ready to capture approved inbox notes.",
    ]


def test_approve_papers_is_idempotent_for_path_input(tmp_path: Path) -> None:
    note_path = tmp_path / "inbox" / "nested" / "attention.md"
    _write_inbox_note(
        note_path,
        paper_id="arxiv:1706.03762",
        title="Attention Is All You Need",
    )

    first = approve_papers_v3(tmp_path, str(note_path))
    second = approve_papers_v3(tmp_path, str(note_path))

    text = note_path.read_text(encoding="utf-8")
    assert first["approved_count"] == 1
    assert second["approved_count"] == 0
    assert second["already_approved_count"] == 1
    assert second["already_approved"][0]["paper_id"] == "arxiv:1706.03762"
    assert text.count("#approved") == 1


def test_approve_papers_all_marks_pending_inbox_notes_only(tmp_path: Path) -> None:
    first_path = tmp_path / "inbox" / "first.md"
    second_path = tmp_path / "inbox" / "second.md"
    helper_path = tmp_path / "inbox" / "_template.md"
    _write_inbox_note(first_path, paper_id="arxiv:1111.11111", title="First Paper")
    _write_inbox_note(second_path, paper_id="arxiv:2222.22222", title="Second Paper")
    _write_inbox_note(helper_path, paper_id="arxiv:3333.33333", title="Helper Paper")

    result = approve_papers_v3(tmp_path, "all")

    assert result["ok"] is True
    assert result["approved_count"] == 2
    assert "#approved" in first_path.read_text(encoding="utf-8")
    assert "#approved" in second_path.read_text(encoding="utf-8")
    assert "#approved" not in helper_path.read_text(encoding="utf-8")


def test_approve_papers_reports_unmatched_chat_selection(tmp_path: Path) -> None:
    note_path = tmp_path / "inbox" / "attention.md"
    _write_inbox_note(
        note_path,
        paper_id="arxiv:1706.03762",
        title="Attention Is All You Need",
    )

    result = approve_papers_v3(tmp_path, "arxiv:9999.99999")

    assert result["ok"] is False
    assert result["approved_count"] == 0
    assert result["errors"] == [
        {
            "input": "arxiv:9999.99999",
            "error": "No matching inbox note found.",
        }
    ]
    assert "#approved" not in note_path.read_text(encoding="utf-8")


def test_approve_papers_tool_offloads_approval_work(monkeypatch) -> None:
    calls: list[str] = []

    async def fake_to_thread(fn, *args, **kwargs):
        calls.append(f"{fn.__name__}:{args[0]}:{args[1]}")
        return fn(*args, **kwargs)

    monkeypatch.setattr(tools_intake.asyncio, "to_thread", fake_to_thread)
    monkeypatch.setattr(tools_intake, "get_vault_path", lambda: "/tmp/vault")

    def fake_approve_papers_v3(*_args):
        return {"ok": True, "approved_count": 1}

    fake_approve_papers_v3.__name__ = "approve_papers_v3"
    monkeypatch.setattr(tools_intake, "approve_papers_v3", fake_approve_papers_v3)

    result = asyncio.run(tools_intake.approve_papers("arxiv:1706.03762"))

    assert result == {"ok": True, "approved_count": 1}
    assert calls == ["approve_papers_v3:/tmp/vault:arxiv:1706.03762"]
