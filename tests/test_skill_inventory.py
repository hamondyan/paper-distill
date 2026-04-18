from __future__ import annotations

from pathlib import Path

import yaml


def test_skill_inventory_is_medium_grained() -> None:
    skills_root = Path(__file__).resolve().parents[1] / "skills"
    skill_files = sorted(skills_root.glob("*/SKILL.md"))
    names = []
    for skill_file in skill_files:
        text = skill_file.read_text(encoding="utf-8")
        frontmatter = text.split("---", 2)[1]
        names.append(yaml.safe_load(frontmatter)["name"])

    assert names == [
        "idea-workbench",
        "knowledge-workbench",
        "paper-distillation",
        "paper-intake",
        "qmd-reference",
    ]


def test_skills_use_progressive_disclosure_references_and_target_size() -> None:
    skills_root = Path(__file__).resolve().parents[1] / "skills"
    for name in (
        "idea-workbench",
        "knowledge-workbench",
        "paper-distillation",
        "paper-intake",
        "qmd-reference",
    ):
        skill_path = skills_root / name / "SKILL.md"
        line_count = len(skill_path.read_text(encoding="utf-8").splitlines())
        references = sorted((skills_root / name / "references").glob("*.md"))

        assert 60 <= line_count <= 90
        assert references
