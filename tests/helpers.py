from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml


def read_markdown(path: Path) -> tuple[dict[str, Any], str]:
    content = path.read_text(encoding="utf-8")
    _, remainder = content.split("---\n", 1)
    frontmatter_text, body = remainder.split("\n---\n", 1)
    return yaml.safe_load(frontmatter_text) or {}, body.strip()


def read_frontmatter(path: Path) -> dict[str, Any]:
    frontmatter, _body = read_markdown(path)
    return frontmatter
