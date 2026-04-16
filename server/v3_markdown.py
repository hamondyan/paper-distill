from __future__ import annotations

import os
import tempfile
from pathlib import Path
from typing import Any

import yaml


def split_frontmatter(text: str) -> tuple[dict[str, Any], str, bool]:
    if not text.startswith("---\n"):
        return {}, text, False

    try:
        _, remainder = text.split("---\n", 1)
        fm_text, body = remainder.split("\n---\n", 1)
    except ValueError:
        return {}, text, False

    try:
        frontmatter = yaml.safe_load(fm_text) or {}
    except yaml.YAMLError:
        return {}, body, True

    if not isinstance(frontmatter, dict):
        return {}, body, True
    return frontmatter, body, True


def render_markdown(frontmatter: dict[str, Any], body: str) -> str:
    payload = dict(frontmatter or {})
    frontmatter_text = yaml.safe_dump(
        payload,
        sort_keys=False,
        allow_unicode=True,
        default_flow_style=False,
    ).strip()
    body_text = body.lstrip("\n").rstrip()
    parts = ["---", frontmatter_text, "---", "", body_text]
    return "\n".join(parts) + "\n"


def atomic_write_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            dir=path.parent,
            prefix=f".{path.stem}.",
            suffix=".tmp",
            delete=False,
        ) as handle:
            tmp_path = Path(handle.name)
            handle.write(content)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(tmp_path, path)
        tmp_path = None
    finally:
        if tmp_path is not None and tmp_path.exists():
            try:
                tmp_path.unlink()
            except FileNotFoundError:
                pass


def write_markdown(path: Path, frontmatter: dict[str, Any], body: str) -> None:
    atomic_write_text(path, render_markdown(frontmatter, body))
