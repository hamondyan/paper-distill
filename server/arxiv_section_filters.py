"""Section title normalization and include/exclude helpers."""
from __future__ import annotations

import re
from typing import Iterable


def normalize_section_title(title: str) -> str:
    normalized = title.strip().lower()
    normalized = re.sub(r"^[\dA-Za-z.\-]+\s+", "", normalized)
    return re.sub(r"\s+", " ", normalized)


def should_keep_section(title: str, *, mode: str = "exclude", selected: Iterable[str] | None = None) -> bool:
    selected_titles = {normalize_section_title(item) for item in (selected or []) if item.strip()}
    if not selected_titles:
        return True
    in_selected = normalize_section_title(title) in selected_titles
    if mode == "include":
        return in_selected
    return not in_selected


def filter_section_titles(titles: list[str], *, mode: str = "exclude", selected: Iterable[str] | None = None) -> list[str]:
    return [title for title in titles if should_keep_section(title, mode=mode, selected=selected)]
