"""Shared follow-up guidance for v3 write operations."""
from __future__ import annotations


FOLLOW_UP: list[str] = [
    "Run qmd update after all writes in this round finish.",
    "Run qmd embed -f after all writes finish if semantic retrieval must reflect the new state immediately.",
]
