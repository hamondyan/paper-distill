from __future__ import annotations

from pathlib import Path

import yaml

from server.v3_memory import write_conversation_memory


def _read_markdown(path: Path) -> tuple[dict, str]:
    content = path.read_text(encoding="utf-8")
    _, remainder = content.split("---\n", 1)
    fm_text, body = remainder.split("\n---\n", 1)
    return yaml.safe_load(fm_text) or {}, body.strip()


def test_write_conversation_memory_creates_insight_asset(
    tmp_path: Path,
    monkeypatch,
) -> None:
    monkeypatch.setattr(
        "server.v3_store.qmd_update",
        lambda *_args, **_kwargs: {"ok": True},
    )

    result = write_conversation_memory(
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


def test_skill_guidance_requires_conversation_memory_tool_writes() -> None:
    knowledge_skill = Path("skills/knowledge-workbench/SKILL.md").read_text(encoding="utf-8")
    intake_skill = Path("skills/paper-intake/SKILL.md").read_text(encoding="utf-8")

    assert "insights/conversations/" in knowledge_skill
    assert "upsert_wiki_page" in knowledge_skill
    assert "verbatim transcripts" in knowledge_skill
    assert "by hand" in knowledge_skill
    assert "insights/conversations/" in intake_skill
    assert "verbatim transcripts" in intake_skill
    assert "by hand" in intake_skill
