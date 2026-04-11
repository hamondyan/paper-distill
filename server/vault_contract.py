"""Canonical Paper Distill vault taxonomy for the Wave 1 cutover."""
from __future__ import annotations

from pathlib import Path
from typing import Final

PAPER_DISTILL_ROOT: Final = "Paper Distill"


ROOT_DIRS: Final[dict[str, str]] = {
    "inbox": "inbox",
    "sources": "sources",
    "sources_evidence": "sources/evidence",
    "zotero": "zotero",
    "zotero_imports": "zotero/imports",
    "wiki": "wiki",
    "papers": "wiki/papers",
    "concepts": "wiki/concepts",
    "methods": "wiki/methods",
    "topics": "wiki/topics",
    "insights": "insights",
    "queries": "insights/queries",
    "ideas": "insights/ideas",
    "dialogues": "insights/dialogues",
    "memory_promotions": "insights/memory-promotions",
    "digests": "insights/digests",
    "memory": "memory",
    "state": ".state",
    "state_ir": ".state/ir",
    "state_memory": ".state/memory",
}

def _query_dir(*parts: str) -> str:
    return str(Path(PAPER_DISTILL_ROOT, *parts))


QUERY_SECTION_PATHS: Final[dict[str, tuple[str, ...]]] = {
    "inbox": (_query_dir(ROOT_DIRS["inbox"]),),
    "source_evidence": (_query_dir(ROOT_DIRS["sources_evidence"]),),
    "sources": (_query_dir(ROOT_DIRS["sources_evidence"]),),
    "papers": (_query_dir(ROOT_DIRS["papers"]),),
    "concepts": (_query_dir(ROOT_DIRS["concepts"]),),
    "methods": (_query_dir(ROOT_DIRS["methods"]),),
    "topics": (_query_dir(ROOT_DIRS["topics"]),),
    "queries": (_query_dir(ROOT_DIRS["queries"]),),
    "digests": (_query_dir(ROOT_DIRS["digests"]),),
}

DEFAULT_QUERY_SECTIONS: Final[tuple[str, ...]] = (
    "inbox",
    "source_evidence",
    "papers",
    "concepts",
    "methods",
    "topics",
)


def paper_distill_root(vault_path: str) -> Path:
    return Path(vault_path).expanduser() / PAPER_DISTILL_ROOT


def root_rel_path(key: str) -> str:
    try:
        return ROOT_DIRS[key]
    except KeyError as exc:
        raise KeyError(f"Unknown Paper Distill root key: {key}") from exc


def root_path(vault_path: str, key: str) -> Path:
    return paper_distill_root(vault_path) / root_rel_path(key)


def query_section_paths(section: str) -> tuple[str, ...]:
    normalized = section.strip().lower().replace("-", "_")
    return QUERY_SECTION_PATHS.get(normalized, ())


def template_contract_context() -> dict[str, object]:
    root = PAPER_DISTILL_ROOT
    return {
        "contract": {
            "root": root,
            "paths": {
                "inbox": f"{root}/{ROOT_DIRS['inbox']}",
                "sources": f"{root}/{ROOT_DIRS['sources']}",
                "source_evidence": f"{root}/{ROOT_DIRS['sources_evidence']}",
                "papers": f"{root}/{ROOT_DIRS['papers']}",
                "concepts": f"{root}/{ROOT_DIRS['concepts']}",
                "methods": f"{root}/{ROOT_DIRS['methods']}",
                "topics": f"{root}/{ROOT_DIRS['topics']}",
                "insights": f"{root}/{ROOT_DIRS['insights']}",
                "queries": f"{root}/{ROOT_DIRS['queries']}",
                "ideas": f"{root}/{ROOT_DIRS['ideas']}",
                "dialogues": f"{root}/{ROOT_DIRS['dialogues']}",
                "memory_promotions": f"{root}/{ROOT_DIRS['memory_promotions']}",
                "digests": f"{root}/{ROOT_DIRS['digests']}",
                "memory": f"{root}/{ROOT_DIRS['memory']}",
                "state": f"{root}/{ROOT_DIRS['state']}",
            },
            "labels": {
                "sources": "Sources",
                "source_evidence": "Source Evidence",
                "insights": "Insights",
                "digests": "Digests",
                "queries": "Query Assets",
                "memory": "Memory Views",
            },
        }
    }
