from __future__ import annotations

from pathlib import Path

from server.v3_conversations import write_conversation_insight
from tests.helpers import read_markdown as _read_markdown


def test_write_conversation_insight_creates_insight_asset(
    tmp_path: Path,
) -> None:
    result = write_conversation_insight(
        vault_path=tmp_path,
        slug="transformer-tension-note",
        body="# Transformer tension\n\nA concise saved insight.\n",
        related_concepts=["Transformer", "Tension", "Attention", "Extra"],
        source_thread="thread-123",
    )

    path = tmp_path / "insights" / "conversations" / "transformer-tension-note.md"
    assert result["ok"] is True
    assert result["follow_up"] == [
        "Run qmd update after all writes in this round finish.",
        "Run qmd embed -f after all writes finish if semantic retrieval must reflect the new state immediately.",
    ]
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
) -> None:
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
) -> None:
    write_conversation_insight(
        vault_path=tmp_path,
        slug="filtered-concepts",
        body="# Filtered concepts\n\nA concise saved insight.\n",
        related_concepts=["", "  ", "Transformer", " Tension ", "Attention"],
    )

    path = tmp_path / "insights" / "conversations" / "filtered-concepts.md"
    frontmatter, _body = _read_markdown(path)
    assert frontmatter["related_concepts_topk"] == ["Transformer", "Tension", "Attention"]


def test_write_conversation_insight_returns_a_fresh_follow_up_list_each_time(
    tmp_path: Path,
) -> None:
    first = write_conversation_insight(
        vault_path=tmp_path,
        slug="fresh-follow-up",
        body="# Fresh follow up\n\nA concise saved insight.\n",
        related_concepts=["Transformer"],
    )
    first["follow_up"].append("mutated")

    second = write_conversation_insight(
        vault_path=tmp_path,
        slug="fresh-follow-up-2",
        body="# Fresh follow up 2\n\nA concise saved insight.\n",
        related_concepts=["Transformer"],
    )

    assert second["follow_up"] == [
        "Run qmd update after all writes in this round finish.",
        "Run qmd embed -f after all writes finish if semantic retrieval must reflect the new state immediately.",
    ]


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
