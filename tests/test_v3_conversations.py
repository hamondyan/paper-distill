from __future__ import annotations

from pathlib import Path

import yaml

from server.v3_conversations import write_conversation_insight


def _read_markdown(path: Path) -> tuple[dict, str]:
    content = path.read_text(encoding="utf-8")
    _, remainder = content.split("---\n", 1)
    fm_text, body = remainder.split("\n---\n", 1)
    return yaml.safe_load(fm_text) or {}, body.strip()


def test_write_conversation_insight_creates_insight_asset(
    tmp_path: Path,
    monkeypatch,
) -> None:
    monkeypatch.setattr(
        "server.v3_store.qmd_update",
        lambda *_args, **_kwargs: {"ok": True},
    )

    result = write_conversation_insight(
        vault_path=tmp_path,
        slug="transformer-tension-note",
        body="# Transformer tension\n\nA concise saved insight.\n",
        related_concepts=["Transformer", "Tension", "Attention", "Extra"],
        source_thread="thread-123",
    )

    path = tmp_path / "insights" / "conversations" / "transformer-tension-note.md"
    assert result["ok"] is True
    assert result["warnings"] == []
    assert path.exists()
    frontmatter, body = _read_markdown(path)
    assert frontmatter["type"] == "conversation"
    assert frontmatter["source_layer"] == "insights"
    assert frontmatter["source_thread"] == "thread-123"
    assert frontmatter["related_concepts_topk"] == ["Transformer", "Tension", "Attention"]
    assert "captured_at" in frontmatter
    assert body == "# Transformer tension\n\nA concise saved insight."


def test_write_conversation_insight_rejects_transcript_shaped_body(
    tmp_path: Path,
    monkeypatch,
) -> None:
    monkeypatch.setattr(
        "server.v3_store.qmd_update",
        lambda *_args, **_kwargs: {"ok": True},
    )

    result = write_conversation_insight(
        vault_path=tmp_path,
        slug="raw-transcript",
        body="User: What is the key idea?\nAssistant: Here is a long answer.\n",
        related_concepts=["Transformer"],
    )

    assert result["ok"] is False
    assert "distilled" in result["error"]
    assert not (tmp_path / "insights" / "conversations" / "raw-transcript.md").exists()


def test_write_conversation_insight_filters_related_concepts_before_topk(
    tmp_path: Path,
    monkeypatch,
) -> None:
    monkeypatch.setattr(
        "server.v3_store.qmd_update",
        lambda *_args, **_kwargs: {"ok": True},
    )

    write_conversation_insight(
        vault_path=tmp_path,
        slug="filtered-concepts",
        body="# Filtered concepts\n\nA concise saved insight.\n",
        related_concepts=["", "  ", "Transformer", " Tension ", "Attention"],
    )

    path = tmp_path / "insights" / "conversations" / "filtered-concepts.md"
    frontmatter, _body = _read_markdown(path)
    assert frontmatter["related_concepts_topk"] == ["Transformer", "Tension", "Attention"]


def test_skill_guidance_requires_conversation_insight_tool_writes() -> None:
    knowledge_skill = Path("skills/knowledge-workbench/SKILL.md").read_text(encoding="utf-8")
    intake_skill = Path("skills/paper-intake/SKILL.md").read_text(encoding="utf-8")

    assert "insights/conversations/" in knowledge_skill
    assert "upsert_wiki_page" in knowledge_skill
    assert "Python conversation insight writer" in knowledge_skill
    assert "verbatim transcripts" in knowledge_skill
    assert "by hand" in knowledge_skill
    assert "insights/conversations/" in intake_skill
    assert "Python write path" in intake_skill
    assert "verbatim transcripts" in intake_skill
    assert "by hand" in intake_skill
