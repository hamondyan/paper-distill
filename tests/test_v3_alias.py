from __future__ import annotations

from pathlib import Path

from server.v3_alias import check_concept_alias_v3


def test_check_concept_alias_prefers_existing_canonical_name(tmp_path: Path) -> None:
    concept_dir = tmp_path / "wiki" / "concepts"
    concept_dir.mkdir(parents=True)
    concept_dir.joinpath("transformer.md").write_text(
        "---\n"
        "type: concept\n"
        "concept: Transformer\n"
        "aliases: [变换器, Transformer模型]\n"
        "status: mature\n"
        "last_updated: \"2026-04-15\"\n"
        "last_tension_update: \"2026-04-15\"\n"
        "sources_topk: [\"arxiv:1706.03762\"]\n"
        "---\n\n"
        "# Transformer\n",
        encoding="utf-8",
    )

    result = check_concept_alias_v3(tmp_path, "Transformer模型")

    assert result["exists"] is True
    assert result["canonical"] == "Transformer"


def test_check_concept_alias_skips_malformed_frontmatter(tmp_path: Path) -> None:
    concept_dir = tmp_path / "wiki" / "concepts"
    concept_dir.mkdir(parents=True)
    concept_dir.joinpath("broken.md").write_text(
        "---\n"
        "aliases: [Broken\n"
        "---\n\n"
        "# Broken\n",
        encoding="utf-8",
    )
    concept_dir.joinpath("transformer.md").write_text(
        "---\n"
        "type: concept\n"
        "concept: Transformer\n"
        "aliases: [变换器]\n"
        "---\n\n"
        "# Transformer\n",
        encoding="utf-8",
    )

    result = check_concept_alias_v3(tmp_path, "变换器")

    assert result["exists"] is True
    assert result["canonical"] == "Transformer"
