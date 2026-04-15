from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any

from server.v3_store import upsert_wiki_page_v3


def write_conversation_memory(
    vault_path: Path,
    slug: str,
    body: str,
    related_concepts: list[str],
    source_thread: str = "current-thread",
) -> dict[str, Any]:
    frontmatter = {
        "type": "conversation",
        "captured_at": datetime.now().astimezone().isoformat(),
        "source_thread": source_thread,
        "related_concepts_topk": [
            concept for concept in related_concepts[:3] if isinstance(concept, str) and concept.strip()
        ],
        "source_layer": "insights",
    }
    return upsert_wiki_page_v3(
        vault_path=vault_path,
        page_type="conversation",
        target=slug,
        frontmatter=frontmatter,
        body=body,
    )
