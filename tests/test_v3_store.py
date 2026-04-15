from __future__ import annotations

from pathlib import Path

import yaml

from server.v3_store import upsert_wiki_page_v3


def _read_markdown(path: Path) -> tuple[dict, str]:
    content = path.read_text(encoding="utf-8")
    _, remainder = content.split("---\n", 1)
    fm_text, body = remainder.split("\n---\n", 1)
    return yaml.safe_load(fm_text) or {}, body.strip()


def test_upsert_wiki_page_writes_markdown_and_returns_warning_when_qmd_update_fails(
    tmp_path: Path,
    monkeypatch,
) -> None:
    monkeypatch.setattr(
        "server.v3_store.qmd_update",
        lambda *_args, **_kwargs: {"ok": False, "error": "qmd update failed"},
    )

    result = upsert_wiki_page_v3(
        vault_path=tmp_path,
        page_type="paper",
        target="attention-is-all-you-need--arxiv-1706.03762",
        frontmatter={
            "type": "paper",
            "paper_id": "arxiv:1706.03762",
            "year": 2017,
            "status": "distilled",
            "key_concepts_topk": ["Transformer"],
            "source_layer": "canon",
        },
        body="# Attention\n\n## Context\nTest",
    )

    path = tmp_path / "wiki" / "papers" / "attention-is-all-you-need--arxiv-1706.03762.md"
    assert result["ok"] is True
    assert result["warnings"] == ["qmd update failed"]
    assert path.exists()
    frontmatter, body = _read_markdown(path)
    assert frontmatter["paper_id"] == "arxiv:1706.03762"
    assert body == "# Attention\n\n## Context\nTest"


def test_upsert_wiki_page_supports_conversation_page_type(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(
        "server.v3_store.qmd_update",
        lambda *_args, **_kwargs: {"ok": True},
    )

    result = upsert_wiki_page_v3(
        vault_path=tmp_path,
        page_type="conversation",
        target="transformer-tension-note",
        frontmatter={"type": "conversation", "related_concepts_topk": ["Transformer"]},
        body="# Transformer tension\n\nA concise saved insight.",
    )

    path = tmp_path / "insights" / "conversations" / "transformer-tension-note.md"
    assert result["ok"] is True
    assert result["warnings"] == []
    assert path.exists()
    frontmatter, body = _read_markdown(path)
    assert frontmatter["type"] == "conversation"
    assert body == "# Transformer tension\n\nA concise saved insight."
