"""Canonical Paper Distill vault taxonomy for the Wave 1 cutover."""
from __future__ import annotations

from pathlib import Path
from typing import Final

PAPER_DISTILL_ROOT: Final = "Paper Distill"


class LegacyTaxonomyWriteError(RuntimeError):
    """Raised when code attempts to write into a retired legacy root."""


ROOT_DIRS: Final[dict[str, str]] = {
    "inbox": "inbox",
    "sources": "sources",
    "sources_evidence": "sources/evidence",
    "sources_notes": "sources/notes",
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
    "verification": "insights/verification",
    "digests": "insights/digests",
    "memory": "memory",
    "state": ".state",
    "state_memory": ".state/memory",
    "compiled_ir": "compiled_ir",
}

RETIRED_ROOT_REDIRECTS: Final[dict[str, str]] = {
    "raw": ROOT_DIRS["sources"],
    "queries": ROOT_DIRS["queries"],
    "daily-log": ROOT_DIRS["digests"],
}

def _query_dir(*parts: str) -> str:
    return str(Path(PAPER_DISTILL_ROOT, *parts))


QUERY_SECTION_PATHS: Final[dict[str, tuple[str, ...]]] = {
    "inbox": (_query_dir(ROOT_DIRS["inbox"]),),
    "raw": (_query_dir(ROOT_DIRS["sources_notes"]),),
    "raw_source": (_query_dir(ROOT_DIRS["sources_evidence"]),),
    "raw_notes": (_query_dir(ROOT_DIRS["sources_notes"]),),
    "sources": (_query_dir(ROOT_DIRS["sources_notes"]),),
    "source_evidence": (_query_dir(ROOT_DIRS["sources_evidence"]),),
    "source_notes": (_query_dir(ROOT_DIRS["sources_notes"]),),
    "papers": (_query_dir(ROOT_DIRS["papers"]),),
    "concepts": (_query_dir(ROOT_DIRS["concepts"]),),
    "methods": (_query_dir(ROOT_DIRS["methods"]),),
    "topics": (_query_dir(ROOT_DIRS["topics"]),),
    "queries": (_query_dir(ROOT_DIRS["queries"]),),
    "digests": (_query_dir(ROOT_DIRS["digests"]),),
}

DEFAULT_QUERY_SECTIONS: Final[tuple[str, ...]] = (
    "inbox",
    "raw_source",
    "raw_notes",
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


def _paper_distill_relative_path(path: Path) -> str | None:
    normalized = Path(path).expanduser()
    parts = normalized.parts
    try:
        root_index = parts.index(PAPER_DISTILL_ROOT)
    except ValueError:
        return None
    remainder = parts[root_index + 1 :]
    if not remainder:
        return ""
    return "/".join(remainder)


def retired_root_for_path(path: Path) -> tuple[str, str] | None:
    rel_path = _paper_distill_relative_path(path)
    if rel_path is None:
        return None
    for retired_root, redirect_root in RETIRED_ROOT_REDIRECTS.items():
        if rel_path == retired_root or rel_path.startswith(f"{retired_root}/"):
            return retired_root, redirect_root
    return None


def assert_supported_write_path(path: Path) -> None:
    retired = retired_root_for_path(path)
    if not retired:
        return
    retired_root, redirect_root = retired
    raise LegacyTaxonomyWriteError(
        "Legacy retired root "
        f"'{PAPER_DISTILL_ROOT}/{retired_root}/' is write-blocked by the Wave 1 "
        "taxonomy contract. "
        f"Write to '{PAPER_DISTILL_ROOT}/{redirect_root}/' instead."
    )


def template_contract_context() -> dict[str, object]:
    root = PAPER_DISTILL_ROOT
    return {
        "contract": {
            "root": root,
            "paths": {
                "inbox": f"{root}/{ROOT_DIRS['inbox']}",
                "sources": f"{root}/{ROOT_DIRS['sources']}",
                "source_evidence": f"{root}/{ROOT_DIRS['sources_evidence']}",
                "source_notes": f"{root}/{ROOT_DIRS['sources_notes']}",
                "papers": f"{root}/{ROOT_DIRS['papers']}",
                "concepts": f"{root}/{ROOT_DIRS['concepts']}",
                "methods": f"{root}/{ROOT_DIRS['methods']}",
                "topics": f"{root}/{ROOT_DIRS['topics']}",
                "insights": f"{root}/{ROOT_DIRS['insights']}",
                "queries": f"{root}/{ROOT_DIRS['queries']}",
                "ideas": f"{root}/{ROOT_DIRS['ideas']}",
                "dialogues": f"{root}/{ROOT_DIRS['dialogues']}",
                "memory_promotions": f"{root}/{ROOT_DIRS['memory_promotions']}",
                "verification": f"{root}/{ROOT_DIRS['verification']}",
                "digests": f"{root}/{ROOT_DIRS['digests']}",
                "memory": f"{root}/{ROOT_DIRS['memory']}",
                "state": f"{root}/{ROOT_DIRS['state']}",
            },
            "labels": {
                "sources": "Sources",
                "source_evidence": "Source Evidence",
                "source_notes": "Source Notes",
                "insights": "Insights",
                "digests": "Digests",
                "queries": "Query Assets",
                "memory": "Memory Views",
            },
        }
    }
