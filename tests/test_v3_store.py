from __future__ import annotations

import asyncio
from pathlib import Path

import yaml

from server import tools_knowledge
from server import tools_health
from server.v3_store import upsert_wiki_page_v3


def _read_markdown(path: Path) -> tuple[dict, str]:
    content = path.read_text(encoding="utf-8")
    _, remainder = content.split("---\n", 1)
    fm_text, body = remainder.split("\n---\n", 1)
    return yaml.safe_load(fm_text) or {}, body.strip()


def test_upsert_wiki_page_writes_markdown_and_returns_follow_up_guidance(
    tmp_path: Path,
    monkeypatch,
) -> None:
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
    assert result["follow_up"] == [
        "Run qmd update after all writes in this round finish.",
        "Run qmd embed -f after all writes finish if semantic retrieval must reflect the new state immediately.",
    ]
    assert "warnings" not in result
    assert path.exists()
    frontmatter, body = _read_markdown(path)
    assert frontmatter["paper_id"] == "arxiv:1706.03762"
    assert body == "# Attention\n\n## Context\nTest"


def test_upsert_wiki_page_supports_conversation_page_type(tmp_path: Path, monkeypatch) -> None:
    result = upsert_wiki_page_v3(
        vault_path=tmp_path,
        page_type="conversation",
        target="transformer-tension-note",
        frontmatter={"type": "conversation", "related_concepts_topk": ["Transformer"]},
        body="# Transformer tension\n\nA concise saved insight.",
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
    assert body == "# Transformer tension\n\nA concise saved insight."


def test_upsert_wiki_page_supports_idea_page_type(tmp_path: Path, monkeypatch) -> None:
    result = upsert_wiki_page_v3(
        vault_path=tmp_path,
        page_type="idea",
        target="active-robot-policy-idea",
        frontmatter={"type": "idea", "idea_state": "active"},
        body="# Active robot policy idea\n\nA grounded research note.",
    )

    path = tmp_path / "insights" / "ideas" / "active-robot-policy-idea.md"
    assert result["ok"] is True
    assert result["follow_up"] == [
        "Run qmd update after all writes in this round finish.",
        "Run qmd embed -f after all writes finish if semantic retrieval must reflect the new state immediately.",
    ]
    assert path.exists()
    frontmatter, body = _read_markdown(path)
    assert frontmatter["type"] == "idea"
    assert body == "# Active robot policy idea\n\nA grounded research note."


def test_upsert_wiki_page_enforces_requested_page_type(tmp_path: Path, monkeypatch) -> None:
    result = upsert_wiki_page_v3(
        vault_path=tmp_path,
        page_type="paper",
        target="attention-is-all-you-need--arxiv-1706.03762",
        frontmatter={"type": "concept", "paper_id": "arxiv:1706.03762"},
        body="# Attention\n",
    )

    path = tmp_path / "wiki" / "papers" / "attention-is-all-you-need--arxiv-1706.03762.md"
    assert result["ok"] is True
    frontmatter, _body = _read_markdown(path)
    assert frontmatter["type"] == "paper"
    assert result["follow_up"] == [
        "Run qmd update after all writes in this round finish.",
        "Run qmd embed -f after all writes finish if semantic retrieval must reflect the new state immediately.",
    ]


def test_upsert_wiki_page_rejects_unknown_type_without_creating_layout(
    tmp_path: Path,
    monkeypatch,
) -> None:
    result = upsert_wiki_page_v3(
        vault_path=tmp_path,
        page_type="method",
        target="demo",
        frontmatter={"type": "method"},
        body="# Demo",
    )

    assert result["ok"] is False
    assert "unsupported page_type" in result["error"]
    assert not (tmp_path / "inbox").exists()


def test_v3_store_does_not_expose_qmd_update() -> None:
    from server import v3_store

    assert not hasattr(v3_store, "qmd_update")


def test_server_entrypoint_registers_knowledge_tools_without_delegate_layer() -> None:
    from server import server as entrypoint

    source = Path(entrypoint.__file__).read_text(encoding="utf-8")
    legacy_runtime_name = "server" + "_" + "runtime"
    upsert_name = "upsert" + "_" + "wiki" + "_" + "page" + "_" + "v3"
    alias_name = "check" + "_" + "concept" + "_" + "alias" + "_" + "v3"

    assert "register_knowledge_tools(mcp)" in source
    assert f"from server import {legacy_runtime_name} as _rt" not in source
    assert upsert_name not in source
    assert alias_name not in source
    assert not hasattr(entrypoint, upsert_name)
    assert not hasattr(entrypoint, alias_name)


def test_check_concept_alias_returns_explicit_error_when_vault_path_missing(
    monkeypatch,
) -> None:
    monkeypatch.setattr(tools_knowledge, "get_vault_path", lambda: "")

    result = asyncio.run(tools_knowledge.check_concept_alias("Transformer"))

    assert result == {
        "ok": False,
        "error": "VAULT_PATH not configured.",
        "exists": False,
        "canonical": "Transformer",
    }


def test_merge_concept_offloads_merge_work(monkeypatch) -> None:
    calls: list[str] = []

    async def fake_to_thread(fn, *args, **kwargs):
        calls.append(fn.__name__)
        return fn(*args, **kwargs)

    monkeypatch.setattr(tools_knowledge.asyncio, "to_thread", fake_to_thread)
    monkeypatch.setattr(tools_knowledge, "get_vault_path", lambda: "/tmp/vault")

    def fake_merge_concept_v3(*_args):
        return {"ok": True}
    fake_merge_concept_v3.__name__ = "merge_concept_v3"

    monkeypatch.setattr(tools_knowledge, "merge_concept_v3", fake_merge_concept_v3)

    result = asyncio.run(tools_knowledge.merge_concept("old", "new"))

    assert result == {"ok": True}
    assert calls == ["merge_concept_v3"]


def test_lint_vault_offloads_lint_work(monkeypatch) -> None:
    calls: list[str] = []

    async def fake_to_thread(fn, *args, **kwargs):
        calls.append(f"{fn.__name__}:{args[0]}")
        return fn(*args, **kwargs)

    monkeypatch.setattr(tools_health.asyncio, "to_thread", fake_to_thread)
    monkeypatch.setattr(tools_health, "get_vault_path", lambda: "/tmp/vault", raising=False)

    def fake_lint_vault_v3(vault_path):
        assert str(vault_path) == "/tmp/vault"
        return {"ok": True, "issues": []}
    fake_lint_vault_v3.__name__ = "lint_vault_v3"

    monkeypatch.setattr(tools_health, "lint_vault_v3", fake_lint_vault_v3)

    result = asyncio.run(tools_health.lint_vault())

    assert result == {"ok": True, "issues": []}
    assert calls == ["lint_vault_v3:/tmp/vault"]
