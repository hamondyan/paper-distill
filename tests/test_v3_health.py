from __future__ import annotations

import asyncio
from pathlib import Path

import yaml

from server.server import mcp
from server.v3_health import lint_vault_v3, merge_concept_v3


def _read_frontmatter(path: Path) -> dict:
    content = path.read_text(encoding="utf-8")
    _, remainder = content.split("---\n", 1)
    fm_text, _body = remainder.split("\n---\n", 1)
    return yaml.safe_load(fm_text) or {}


def test_lint_vault_flags_repeated_links_and_oversized_frontmatter(tmp_path: Path) -> None:
    paper_dir = tmp_path / "wiki" / "papers"
    paper_dir.mkdir(parents=True)
    paper_dir.joinpath("demo.md").write_text(
        "---\n"
        + "\n".join([f"k{i}: v" for i in range(25)])
        + "\n---\n\n"
        "[[Transformer]] [[Transformer]]\n",
        encoding="utf-8",
    )

    result = lint_vault_v3(tmp_path)

    assert any(issue["code"] == "frontmatter_too_large" for issue in result["issues"])
    assert any(issue["code"] == "repeated_link" for issue in result["issues"])


def test_lint_vault_flags_repeated_links_across_paragraph_lines(tmp_path: Path) -> None:
    concept_dir = tmp_path / "wiki" / "concepts"
    paper_dir = tmp_path / "wiki" / "papers"
    concept_dir.mkdir(parents=True)
    paper_dir.mkdir(parents=True)
    concept_dir.joinpath("transformer.md").write_text("# Transformer\n", encoding="utf-8")
    paper_dir.joinpath("demo.md").write_text(
        "# Demo\n\n"
        "The first mention is [[Transformer]]\n"
        "and the same paragraph repeats [[Transformer]].\n",
        encoding="utf-8",
    )

    result = lint_vault_v3(tmp_path)

    assert any(issue["code"] == "repeated_link" for issue in result["issues"])


def test_lint_vault_flags_dead_links_alias_ambiguity_and_footer_linking(
    tmp_path: Path,
) -> None:
    concept_dir = tmp_path / "wiki" / "concepts"
    paper_dir = tmp_path / "wiki" / "papers"
    concept_dir.mkdir(parents=True)
    paper_dir.mkdir(parents=True)
    concept_dir.joinpath("transformer.md").write_text(
        "---\n"
        "type: concept\n"
        "concept: Transformer\n"
        "aliases: [attention model]\n"
        "---\n\n"
        "# Transformer\n",
        encoding="utf-8",
    )
    concept_dir.joinpath("attention.md").write_text(
        "---\n"
        "type: concept\n"
        "concept: Attention\n"
        "aliases: [attention model]\n"
        "---\n\n"
        "# Attention\n",
        encoding="utf-8",
    )
    paper_dir.joinpath("demo.md").write_text(
        "# Demo\n\n"
        "Missing target: [[Nonexistent Concept]]\n\n"
        "Related: [[Transformer]] [[Attention]] [[LLM]] [[RAG]]\n",
        encoding="utf-8",
    )

    result = lint_vault_v3(tmp_path)
    codes = {issue["code"] for issue in result["issues"]}

    assert {"dead_link", "alias_ambiguity", "template_footer_link"} <= codes


def test_lint_vault_flags_alias_that_conflicts_with_canonical(tmp_path: Path) -> None:
    concept_dir = tmp_path / "wiki" / "concepts"
    concept_dir.mkdir(parents=True)
    concept_dir.joinpath("transformer.md").write_text(
        "---\n"
        "type: concept\n"
        "concept: Transformer\n"
        "aliases: []\n"
        "---\n\n"
        "# Transformer\n",
        encoding="utf-8",
    )
    concept_dir.joinpath("attention.md").write_text(
        "---\n"
        "type: concept\n"
        "concept: Attention\n"
        "aliases: [Transformer]\n"
        "---\n\n"
        "# Attention\n",
        encoding="utf-8",
    )

    result = lint_vault_v3(tmp_path)

    assert any(issue["code"] == "alias_ambiguity" for issue in result["issues"])


def test_lint_vault_flags_balanced_malformed_links_and_split_footer_links(
    tmp_path: Path,
) -> None:
    concept_dir = tmp_path / "wiki" / "concepts"
    paper_dir = tmp_path / "wiki" / "papers"
    concept_dir.mkdir(parents=True)
    paper_dir.mkdir(parents=True)
    concept_dir.joinpath("transformer.md").write_text("# Transformer\n", encoding="utf-8")
    concept_dir.joinpath("attention.md").write_text("# Attention\n", encoding="utf-8")
    concept_dir.joinpath("rag.md").write_text("# RAG\n", encoding="utf-8")
    paper_dir.joinpath("demo.md").write_text(
        "# Demo\n\n"
        "Malformed but balanced: [[|Empty Target]]\n\n"
        "Related:\n"
        "- [[Transformer]]\n"
        "- [[Attention]]\n"
        "- [[RAG]]\n",
        encoding="utf-8",
    )

    result = lint_vault_v3(tmp_path)
    codes = {issue["code"] for issue in result["issues"]}

    assert {"malformed_link", "template_footer_link"} <= codes


def test_lint_vault_flags_regex_shaped_malformed_links(tmp_path: Path) -> None:
    paper_dir = tmp_path / "wiki" / "papers"
    paper_dir.mkdir(parents=True)
    paper_dir.joinpath("demo.md").write_text(
        "# Demo\n\n"
        "This is balanced but not a valid wikilink: [[Bad[Target]]\n",
        encoding="utf-8",
    )

    result = lint_vault_v3(tmp_path)

    assert any(issue["code"] == "malformed_link" for issue in result["issues"])


def test_merge_concept_rewrites_links_updates_aliases_and_returns_follow_up(
    tmp_path: Path,
    monkeypatch,
) -> None:
    concept_dir = tmp_path / "wiki" / "concepts"
    paper_dir = tmp_path / "wiki" / "papers"
    concept_dir.mkdir(parents=True)
    paper_dir.mkdir(parents=True)

    concept_dir.joinpath("llm.md").write_text(
        "---\n"
        "type: concept\n"
        "concept: LLM\n"
        "aliases: []\n"
        "status: mature\n"
        "last_updated: \"2026-04-15\"\n"
        "last_tension_update: \"2026-04-15\"\n"
        "sources_topk: []\n"
        "---\n\n"
        "# LLM\n",
        encoding="utf-8",
    )
    paper_dir.joinpath("demo.md").write_text("[[大型语言模型]]\n", encoding="utf-8")

    result = merge_concept_v3(tmp_path, "大型语言模型", "llm")

    assert result["ok"] is True
    assert result["follow_up"] == [
        "Run qmd update after all writes in this round finish.",
        "Run qmd embed -f after all writes finish if semantic retrieval must reflect the new state immediately.",
    ]
    assert "update" not in result
    assert "reembed" not in result
    assert paper_dir.joinpath("demo.md").read_text(encoding="utf-8") == "[[llm]]\n"
    frontmatter = _read_frontmatter(concept_dir / "llm.md")
    assert "大型语言模型" in frontmatter["aliases"]


def test_merge_concept_fails_closed_when_target_resolution_is_ambiguous(
    tmp_path: Path,
    monkeypatch,
) -> None:
    concept_dir = tmp_path / "wiki" / "concepts"
    paper_dir = tmp_path / "wiki" / "papers"
    concept_dir.mkdir(parents=True)
    paper_dir.mkdir(parents=True)
    concept_dir.joinpath("a.md").write_text(
        "---\ntype: concept\nconcept: Shared\naliases: []\n---\n\n# Shared\n",
        encoding="utf-8",
    )
    concept_dir.joinpath("b.md").write_text(
        "---\ntype: concept\nconcept: Shared\naliases: []\n---\n\n# Shared\n",
        encoding="utf-8",
    )
    paper_path = paper_dir / "demo.md"
    paper_path.write_text("[[Old Concept]]\n", encoding="utf-8")

    result = merge_concept_v3(tmp_path, "Old Concept", "Shared")

    assert result["ok"] is False
    assert "ambiguous target concept" in result["error"]
    assert paper_path.read_text(encoding="utf-8") == "[[Old Concept]]\n"


def test_merge_concept_returns_follow_up_guidance_on_success(
    tmp_path: Path,
    monkeypatch,
) -> None:
    concept_dir = tmp_path / "wiki" / "concepts"
    paper_dir = tmp_path / "wiki" / "papers"
    concept_dir.mkdir(parents=True)
    paper_dir.mkdir(parents=True)
    concept_dir.joinpath("llm.md").write_text(
        "---\ntype: concept\nconcept: LLM\naliases: []\n---\n\n# LLM\n",
        encoding="utf-8",
    )
    paper_dir.joinpath("demo.md").write_text("[[大型语言模型]]\n", encoding="utf-8")

    result = merge_concept_v3(tmp_path, "大型语言模型", "llm")

    assert result["ok"] is True
    assert result["follow_up"] == [
        "Run qmd update after all writes in this round finish.",
        "Run qmd embed -f after all writes finish if semantic retrieval must reflect the new state immediately.",
    ]


def test_v3_health_does_not_expose_qmd_side_effect_helpers() -> None:
    from server import v3_health

    assert not hasattr(v3_health, "qmd_update")
    assert not hasattr(v3_health, "qmd_reembed_force")


def test_merge_concept_returns_a_fresh_follow_up_list_each_time(
    tmp_path: Path,
) -> None:
    concept_dir = tmp_path / "wiki" / "concepts"
    paper_dir = tmp_path / "wiki" / "papers"
    concept_dir.mkdir(parents=True)
    paper_dir.mkdir(parents=True)
    concept_dir.joinpath("llm.md").write_text(
        "---\ntype: concept\nconcept: LLM\naliases: []\n---\n\n# LLM\n",
        encoding="utf-8",
    )
    paper_dir.joinpath("demo.md").write_text("[[大型语言模型]]\n", encoding="utf-8")

    first = merge_concept_v3(tmp_path, "大型语言模型", "llm")
    first["follow_up"].append("mutated")

    second = merge_concept_v3(tmp_path, "大型语言模型", "llm")

    assert second["follow_up"] == [
        "Run qmd update after all writes in this round finish.",
        "Run qmd embed -f after all writes finish if semantic retrieval must reflect the new state immediately.",
    ]


def test_mcp_lists_v3_health_surface_names() -> None:
    tools = asyncio.run(mcp.list_tools())
    names = {tool.name for tool in tools}

    assert {"lint_vault", "merge_concept"} <= names
    assert "kb_update_index" not in names
    assert "kb_reembed_force" not in names
