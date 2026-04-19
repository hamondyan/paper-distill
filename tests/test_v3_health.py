from __future__ import annotations

import asyncio
from datetime import date
from pathlib import Path

from server.server import mcp
from server.v3_health import lint_vault_v3, merge_concept_v3
from tests.helpers import read_frontmatter as _read_frontmatter


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


def test_lint_vault_flags_paper_without_concept_link(tmp_path: Path) -> None:
    concept_dir = tmp_path / "wiki" / "concepts"
    paper_dir = tmp_path / "wiki" / "papers"
    concept_dir.mkdir(parents=True)
    paper_dir.mkdir(parents=True)
    concept_dir.joinpath("transformer.md").write_text(
        "---\ntype: concept\nconcept: Transformer\naliases: []\n---\n\n# Transformer\n",
        encoding="utf-8",
    )
    paper_dir.joinpath("attention.md").write_text(
        "---\n"
        "type: paper\n"
        "paper_id: arxiv:1706.03762\n"
        "title: Attention Is All You Need\n"
        "key_concepts_topk: [Transformer]\n"
        "---\n\n"
        "# Attention Is All You Need\n\n"
        "This paper summary forgot to link its concept.\n",
        encoding="utf-8",
    )

    result = lint_vault_v3(tmp_path)

    assert any(issue["code"] == "paper_missing_concept_link" for issue in result["issues"])


def test_lint_vault_flags_paper_key_concept_not_linked_in_body(tmp_path: Path) -> None:
    concept_dir = tmp_path / "wiki" / "concepts"
    paper_dir = tmp_path / "wiki" / "papers"
    concept_dir.mkdir(parents=True)
    paper_dir.mkdir(parents=True)
    concept_dir.joinpath("transformer.md").write_text("# Transformer\n", encoding="utf-8")
    concept_dir.joinpath("attention.md").write_text("# Attention\n", encoding="utf-8")
    paper_dir.joinpath("attention.md").write_text(
        "---\n"
        "type: paper\n"
        "paper_id: arxiv:1706.03762\n"
        "title: Attention Is All You Need\n"
        "key_concepts_topk: [Transformer]\n"
        "---\n\n"
        "# Attention Is All You Need\n\n"
        "This page links [[Attention]] but not its key concept.\n",
        encoding="utf-8",
    )

    result = lint_vault_v3(tmp_path)

    assert any(issue["code"] == "paper_key_concept_unlinked" for issue in result["issues"])


def test_lint_vault_flags_paper_with_too_many_concept_links(tmp_path: Path) -> None:
    concept_dir = tmp_path / "wiki" / "concepts"
    paper_dir = tmp_path / "wiki" / "papers"
    concept_dir.mkdir(parents=True)
    paper_dir.mkdir(parents=True)
    for concept in ("A", "B", "C", "D", "E", "F"):
        concept_dir.joinpath(f"{concept.lower()}.md").write_text(f"# {concept}\n", encoding="utf-8")
    paper_dir.joinpath("dense.md").write_text(
        "---\n"
        "type: paper\n"
        "paper_id: arxiv:0000.00000\n"
        "title: Dense Paper\n"
        "key_concepts_topk: [A, B, C, D, E, F]\n"
        "---\n\n"
        "# Dense Paper\n\n"
        "[[A]] [[B]] [[C]] [[D]] [[E]] [[F]]\n",
        encoding="utf-8",
    )

    result = lint_vault_v3(tmp_path)

    assert any(issue["code"] == "paper_too_many_concept_links" for issue in result["issues"])


def test_lint_vault_flags_decorative_category_like_concept_link(tmp_path: Path) -> None:
    concept_dir = tmp_path / "wiki" / "concepts"
    paper_dir = tmp_path / "wiki" / "papers"
    evidence_dir = tmp_path / "raw" / "evidence"
    concept_dir.mkdir(parents=True)
    paper_dir.mkdir(parents=True)
    evidence_dir.mkdir(parents=True)
    concept_dir.joinpath("vision-language-action-models.md").write_text(
        "---\n"
        "type: concept\n"
        "concept: Vision-Language-Action Models\n"
        "aliases: []\n"
        "source_layer: wiki\n"
        "related_papers_topk: [arxiv:2401.00001]\n"
        "---\n\n"
        "# Vision-Language-Action Models\n",
        encoding="utf-8",
    )
    paper_dir.joinpath("demo.md").write_text(
        "---\n"
        "type: paper\n"
        "paper_id: arxiv:2401.00001\n"
        "title: Demo VLA Paper\n"
        "year: 2024\n"
        "venue: arXiv\n"
        "source_layer: wiki\n"
        "key_concepts_topk: [Vision-Language-Action Models]\n"
        "---\n\n"
        "# Demo VLA Paper\n\n"
        "This paper is broadly related to [[Vision-Language-Action Models]].\n",
        encoding="utf-8",
    )
    evidence_dir.joinpath("demo.md").write_text(
        "---\ntype: raw_evidence\npaper_id: arxiv:2401.00001\n---\n\n# Evidence\n",
        encoding="utf-8",
    )

    result = lint_vault_v3(tmp_path)
    decorative = [issue for issue in result["issues"] if issue["code"] == "decorative_concept_link"]

    assert decorative
    assert decorative[0]["target"] == "Vision-Language-Action Models"
    assert decorative[0]["severity"] == "warning"
    assert "structurally valid" in decorative[0]["message"]


def test_lint_vault_accepts_supported_category_like_concept_link(tmp_path: Path) -> None:
    concept_dir = tmp_path / "wiki" / "concepts"
    paper_dir = tmp_path / "wiki" / "papers"
    evidence_dir = tmp_path / "raw" / "evidence"
    concept_dir.mkdir(parents=True)
    paper_dir.mkdir(parents=True)
    evidence_dir.mkdir(parents=True)
    concept_dir.joinpath("vision-language-action-models.md").write_text(
        "---\n"
        "type: concept\n"
        "concept: Vision-Language-Action Models\n"
        "aliases: []\n"
        "source_layer: wiki\n"
        "related_papers_topk: [arxiv:2401.00001]\n"
        "---\n\n"
        "# Vision-Language-Action Models\n",
        encoding="utf-8",
    )
    paper_dir.joinpath("demo.md").write_text(
        "---\n"
        "type: paper\n"
        "paper_id: arxiv:2401.00001\n"
        "title: Demo VLA Paper\n"
        "year: 2024\n"
        "venue: arXiv\n"
        "source_layer: wiki\n"
        "key_concepts_topk: [Vision-Language-Action Models]\n"
        "---\n\n"
        "# Demo VLA Paper\n\n"
        "The paper defines [[Vision-Language-Action Models]] as policies that map images "
        "and language instructions to robot actions for manipulation tasks.\n",
        encoding="utf-8",
    )
    evidence_dir.joinpath("demo.md").write_text(
        "---\ntype: raw_evidence\npaper_id: arxiv:2401.00001\n---\n\n# Evidence\n",
        encoding="utf-8",
    )

    result = lint_vault_v3(tmp_path)

    assert not any(issue["code"] == "decorative_concept_link" for issue in result["issues"])


def test_lint_vault_flags_concept_without_supporting_paper(tmp_path: Path) -> None:
    concept_dir = tmp_path / "wiki" / "concepts"
    concept_dir.mkdir(parents=True)
    concept_dir.joinpath("transformer.md").write_text(
        "---\n"
        "type: concept\n"
        "concept: Transformer\n"
        "aliases: []\n"
        "source_layer: canon\n"
        "related_papers_topk: []\n"
        "---\n\n"
        "# Transformer\n",
        encoding="utf-8",
    )

    result = lint_vault_v3(tmp_path)

    assert any(issue["code"] == "concept_missing_supporting_paper" for issue in result["issues"])


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


def test_lint_vault_flags_paper_missing_required_fields(tmp_path: Path) -> None:
    concept_dir = tmp_path / "wiki" / "concepts"
    paper_dir = tmp_path / "wiki" / "papers"
    concept_dir.mkdir(parents=True)
    paper_dir.mkdir(parents=True)
    concept_dir.joinpath("transformer.md").write_text("# Transformer\n", encoding="utf-8")
    paper_dir.joinpath("demo.md").write_text(
        "---\n"
        "type: paper\n"
        "paper_id: arxiv:0000.0000\n"
        "title: Demo\n"
        "---\n\n"
        "# Demo\n\nSee [[Transformer]].\n",
        encoding="utf-8",
    )

    result = lint_vault_v3(tmp_path)
    field_issues = [i for i in result["issues"] if i["code"] == "paper_missing_required_fields"]

    assert field_issues, result["issues"]
    missing = field_issues[0]["fields"]
    assert "venue" in missing
    assert "source_layer" in missing
    assert "year" in missing
    assert "key_concepts_topk" in missing


def test_lint_vault_flags_paper_without_raw_evidence(tmp_path: Path) -> None:
    concept_dir = tmp_path / "wiki" / "concepts"
    paper_dir = tmp_path / "wiki" / "papers"
    concept_dir.mkdir(parents=True)
    paper_dir.mkdir(parents=True)
    concept_dir.joinpath("transformer.md").write_text("# Transformer\n", encoding="utf-8")
    paper_dir.joinpath("demo.md").write_text(
        "---\n"
        "type: paper\n"
        "paper_id: arxiv:1706.03762\n"
        "title: Attention Is All You Need\n"
        "year: 2017\n"
        "venue: NeurIPS\n"
        "source_layer: wiki\n"
        "key_concepts_topk: [Transformer]\n"
        "---\n\n"
        "# Attention Is All You Need\n\nSee [[Transformer]].\n",
        encoding="utf-8",
    )

    result = lint_vault_v3(tmp_path)
    orphan_issues = [i for i in result["issues"] if i["code"] == "paper_without_raw_evidence"]

    assert orphan_issues
    assert orphan_issues[0]["paper_id"] == "arxiv:1706.03762"


def test_lint_vault_does_not_flag_paper_with_matching_raw_evidence(tmp_path: Path) -> None:
    concept_dir = tmp_path / "wiki" / "concepts"
    paper_dir = tmp_path / "wiki" / "papers"
    evidence_dir = tmp_path / "raw" / "evidence"
    concept_dir.mkdir(parents=True)
    paper_dir.mkdir(parents=True)
    evidence_dir.mkdir(parents=True)
    concept_dir.joinpath("transformer.md").write_text("# Transformer\n", encoding="utf-8")
    paper_dir.joinpath("demo.md").write_text(
        "---\n"
        "type: paper\n"
        "paper_id: arxiv:1706.03762\n"
        "title: Attention Is All You Need\n"
        "year: 2017\n"
        "venue: NeurIPS\n"
        "source_layer: wiki\n"
        "key_concepts_topk: [Transformer]\n"
        "---\n\n"
        "# Attention Is All You Need\n\nSee [[Transformer]].\n",
        encoding="utf-8",
    )
    evidence_dir.joinpath("demo.md").write_text(
        "---\ntype: raw_evidence\npaper_id: arxiv:1706.03762\n---\n\n# Evidence\n",
        encoding="utf-8",
    )

    result = lint_vault_v3(tmp_path)

    assert not any(i["code"] == "paper_without_raw_evidence" for i in result["issues"])


def test_lint_vault_ignores_retired_inbox_notes(tmp_path: Path) -> None:
    inbox_dir = tmp_path / "inbox"
    inbox_dir.mkdir(parents=True)
    inbox_dir.joinpath("stale.md").write_text(
        '---\ntype: inbox_stub\ndiscovered_at: "2025-01-01"\n---\n\nsome note\n',
        encoding="utf-8",
    )

    result = lint_vault_v3(tmp_path, today=date(2026, 4, 18))

    assert not any(i["code"] == "inbox_stale" for i in result["issues"])


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
