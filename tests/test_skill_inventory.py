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

    assert names == ["idea-workbench", "knowledge-workbench", "paper-intake"]
