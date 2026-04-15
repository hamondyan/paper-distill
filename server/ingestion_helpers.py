"""Clean ingestion helpers with no circular dependencies.

Only _ingestion_paths and _wiki_body_payload live here.
Functions that call MCP tool functions (fetch_pdf_text, commit_compile_result)
remain in server_runtime.py until a dependency-injection refactoring is done.
"""
from __future__ import annotations

from pathlib import Path

from server.research_item import ResearchItem
from server.vault_ops import (
    citekey_for_paper,
    source_evidence_path,
    source_evidence_sidecar_path,
    wiki_paper_path,
)


def _ingestion_paths(vault_path: str, paper: dict) -> tuple[str, Path, Path, Path, str, str, str]:
    citekey = citekey_for_paper(paper)
    source_path = source_evidence_path(vault_path, citekey)
    source_structured_path = source_evidence_sidecar_path(vault_path, citekey)
    wiki_path = wiki_paper_path(vault_path, citekey)
    source_rel_path = str(source_path.relative_to(Path(vault_path)))
    source_structured_rel_path = str(source_structured_path.relative_to(Path(vault_path)))
    wiki_rel_path = str(wiki_path.relative_to(Path(vault_path)))
    return citekey, source_path, source_structured_path, wiki_path, source_rel_path, source_structured_rel_path, wiki_rel_path


def _wiki_body_payload(
    research_item: ResearchItem,
    paper: dict,
    source_rel_path: str,
    source_structured_rel_path: str,
    zotero_mode: str,
    zotero_status: str,
    zotero_import_path: str,
    zotero_key: str,
    zotero_uri: str,
    capture_fidelity: str,
    dnl_note: dict,
) -> dict:
    note_paper = {
        "title": research_item.title,
        "authors_short": ", ".join(research_item.authors[:3]) or "Unknown authors",
        "year": research_item.year,
        "venue": research_item.venue,
        "citekey": research_item.citekey,
        "source_evidence_path": source_rel_path,
        "source_assets_path": source_structured_rel_path,
        "zotero_mode": zotero_mode,
        "zotero_status": zotero_status,
        "zotero_import_path": zotero_import_path,
        "zotero_uri": zotero_uri,
        "zotero_key": zotero_key,
        "capture_fidelity": capture_fidelity,
        "page_state": "pending-llm",
        "confidence": 0.0,
        "why_read": paper.get("tldr") or paper.get("abstract", "")[:200] or "Pending LLM enrichment.",
        "summary": paper.get("abstract", ""),
        "insights": "",
        "connections": "",
    }
    return {
        "paper": note_paper,
        "sections": dnl_note.get("sections", {}),
    }
