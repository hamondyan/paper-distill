from __future__ import annotations

import re
from datetime import datetime
from pathlib import Path
from typing import Any

from server.v3_store import upsert_wiki_page_v3


_TRANSCRIPT_SPEAKER_RE = re.compile(
    r"^\s*(user|assistant|system|human|ai|用户|助手)[:：]",
    re.IGNORECASE,
)


def _looks_like_transcript(body: str) -> bool:
    speaker_lines = [
        line for line in body.splitlines()
        if _TRANSCRIPT_SPEAKER_RE.match(line)
    ]
    return len(speaker_lines) >= 2


def _related_concepts_topk(related_concepts: list[str]) -> list[str]:
    cleaned = [
        concept.strip()
        for concept in related_concepts
        if isinstance(concept, str) and concept.strip()
    ]
    return cleaned[:3]


def write_conversation_memory(
    vault_path: Path,
    slug: str,
    body: str,
    related_concepts: list[str],
    source_thread: str = "current-thread",
) -> dict[str, Any]:
    if _looks_like_transcript(body):
        return {
            "ok": False,
            "error": "conversation memory must be a distilled insight, not a verbatim transcript",
            "warnings": [],
        }

    frontmatter = {
        "type": "conversation",
        "captured_at": datetime.now().astimezone().isoformat(),
        "source_thread": source_thread,
        "related_concepts_topk": _related_concepts_topk(related_concepts),
        "source_layer": "insights",
    }
    return upsert_wiki_page_v3(
        vault_path=vault_path,
        page_type="conversation",
        target=slug,
        frontmatter=frontmatter,
        body=body,
    )
