"""LLM-driven CRGP section tools.

Provides two pure-Python helpers that are exposed as MCP tools:

    prepare_crgp_context  — reads source evidence + metadata so the LLM can
                            generate grounded CRGP sections
    save_crgp_sections    — persists LLM-generated sections to the wiki MD
                            and the SQLite compile_state; optionally accepts a
                            ``metadata`` dict (candidate_concepts +
                            tension_fields) to also write the IR files and
                            auto-register concepts so that idea-analyze can
                            pick up this paper's tension signals.
"""
from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

import yaml

from server.compile_ir import commit_compile_result, get_compile_state
from server.vault_contract import paper_distill_root
from server.vault_ops import build_wiki_paper_body, wiki_paper_path

LOG = logging.getLogger(__name__)

CRGP_SECTION_KEYS = (
    "Context",
    "Related Work",
    "Gap",
    "Proposal",
    "Key Results",
    "Discussion",
    "Next Steps",
)

_SOURCE_FM_SEPARATOR = "\n---\n"
_MAX_SOURCE_CHARS = 40_000


def _read_frontmatter(path: Path) -> dict[str, Any]:
    try:
        content = path.read_text(encoding="utf-8")
    except OSError:
        return {}
    if not content.startswith("---\n"):
        return {}
    _, remainder = content.split("---\n", 1)
    if _SOURCE_FM_SEPARATOR not in remainder:
        return {}
    fm_text, _ = remainder.split(_SOURCE_FM_SEPARATOR, 1)
    result = yaml.safe_load(fm_text) or {}
    return result if isinstance(result, dict) else {}


def _strip_frontmatter_body(path: Path) -> str:
    """Return only the markdown body (after the closing --- fence)."""
    try:
        content = path.read_text(encoding="utf-8")
    except OSError:
        return ""
    if not content.startswith("---\n"):
        return content
    _, remainder = content.split("---\n", 1)
    if _SOURCE_FM_SEPARATOR not in remainder:
        return remainder
    _, body = remainder.split(_SOURCE_FM_SEPARATOR, 1)
    return body.strip()


def _find_source_evidence(vault_path: str, citekey: str) -> Path | None:
    """Return the source evidence path for a citekey by globbing sources/evidence/.

    Globs from the ``Paper Distill`` sub-root so the path is correct
    regardless of whether vault_path points to the Obsidian vault root or
    a nested directory.
    """
    pd_root = paper_distill_root(vault_path)
    matches = list(pd_root.glob(f"sources/evidence/**/{citekey}.md"))
    return matches[0] if matches else None


def prepare_crgp_context(vault_path: str, citekey: str) -> dict[str, Any]:
    """Return all source evidence and metadata needed for LLM CRGP generation.

    The returned dict contains:
        citekey            — the paper citekey
        paper_metadata     — title, authors, year, venue, abstract
        source_markdown    — cleaned arXiv body (truncated to 40k chars)
        current_sections   — previously stored managed sections (may be empty)
        error              — non-empty string if the context could not be loaded

    Args:
        vault_path: Absolute path to the vault root.
        citekey:    Paper citekey (e.g. "brohan2023rt2").
    """
    vault = Path(vault_path)
    wiki_path = wiki_paper_path(vault_path, citekey)

    if wiki_path.exists():
        fm = _read_frontmatter(wiki_path)
        if not fm:
            return {"error": f"Could not parse frontmatter for '{citekey}'"}
        source_rel = fm.get("source_evidence_path", "")
    else:
        # Wiki page not yet created — look up source evidence directly
        source_evidence_file = _find_source_evidence(vault_path, citekey)
        if not source_evidence_file:
            return {"error": f"No source evidence found for citekey '{citekey}'"}
        fm = _read_frontmatter(source_evidence_file)
        if not fm:
            return {"error": f"Could not parse source evidence frontmatter for '{citekey}'"}
        source_rel = str(source_evidence_file.relative_to(vault))

    source_path = Path(vault_path) / source_rel if source_rel else None

    source_markdown = ""
    if source_path and source_path.exists():
        source_markdown = _strip_frontmatter_body(source_path)[:_MAX_SOURCE_CHARS]

    state = get_compile_state(vault_path, citekey)
    current_sections: dict[str, str] = {}
    if state:
        try:
            current_sections = json.loads(state.get("managed_blocks_json") or "{}")
        except (json.JSONDecodeError, TypeError):
            pass

    authors_raw = fm.get("authors", [])
    authors = authors_raw if isinstance(authors_raw, list) else [authors_raw]

    return {
        "citekey": citekey,
        "paper_metadata": {
            "title": fm.get("title", ""),
            "authors": authors,
            "year": fm.get("year"),
            "venue": fm.get("venue", ""),
            "abstract": fm.get("abstract", ""),
        },
        "source_markdown": source_markdown,
        "current_sections": current_sections,
        "error": "",
    }


def save_crgp_sections(
    vault_path: str,
    citekey: str,
    sections: dict[str, str],
    confidence: float = 0.93,
    metadata: dict | None = None,
) -> dict[str, Any]:
    """Persist LLM-generated CRGP sections to the wiki MD and SQLite.

    Validates that all 7 required section keys are present, then rebuilds
    the wiki page body and calls commit_compile_result to atomically update
    both the markdown file and the compile_state record (version bump,
    managed_blocks_json, content_hash).

    If ``metadata`` is provided, the function also writes an IR JSON and
    resolves candidate concepts before committing, so that the paper's
    tension signals become visible to idea-analyze / aggregate_tension_signals.

    Args:
        vault_path: Absolute path to the vault root.
        citekey:    Paper citekey.
        sections:   Dict with all 7 CRGP section keys mapped to markdown text.
        confidence: Confidence score to record (default 0.93 for LLM-generated).
        metadata:   Optional structured metadata dict with keys:
                        candidate_concepts  – list[{name, type, aliases?}]
                        tension_fields      – {limitations, assumptions,
                                               open_questions, negative_results,
                                               failure_modes?, transfer_constraints?}
                        benchmark_scope?    – str
                        claimed_novelty?    – str
                        topics?             – list[str]
                    When provided, write_ir() + resolve_ir() are called before
                    commit_compile_result(), and ir_path is recorded in
                    compile_state. IR failures are non-fatal: the wiki page is
                    still written and warnings are returned in ``ir_warnings``.

    Returns dict with keys: written, path, compile_version, conflict_detected,
    conflicts (if any), ir_warnings (if any), error (if any).
    """
    missing = [k for k in CRGP_SECTION_KEYS if k not in sections]
    if missing:
        return {"error": f"sections dict is missing required keys: {missing}"}

    vault = Path(vault_path)
    wiki_path = wiki_paper_path(vault_path, citekey)

    if not wiki_path.exists():
        # Wiki page not yet created — build frontmatter from source evidence
        source_evidence_file = _find_source_evidence(vault_path, citekey)
        if not source_evidence_file:
            return {"error": f"No source evidence found for citekey '{citekey}'"}
        source_fm = _read_frontmatter(source_evidence_file)
        if not source_fm:
            return {"error": f"Could not parse source evidence frontmatter for '{citekey}'"}
        source_rel = str(source_evidence_file.relative_to(vault))
        fm: dict[str, Any] = {
            "paper_id": source_fm.get("paper_id", ""),
            "citekey": citekey,
            "title": source_fm.get("title", ""),
            "authors": source_fm.get("authors", []),
            "year": source_fm.get("year"),
            "doi": source_fm.get("doi", ""),
            "arxiv_id": source_fm.get("arxiv_id", ""),
            "venue": source_fm.get("venue", ""),
            "venue_normalized": source_fm.get("venue_normalized", ""),
            "venue_tier": source_fm.get("venue_tier", "unknown"),
            "venue_source": source_fm.get("venue_source", ""),
            "topics": source_fm.get("topics", []),
            "canonical_html_url": source_fm.get("canonical_html_url", ""),
            "canonical_pdf_url": source_fm.get("canonical_pdf_url", ""),
            "canonical_item_url": source_fm.get("canonical_item_url", ""),
            "source_evidence_path": source_rel,
            "source_assets_path": source_fm.get("source_structured_path", ""),
            "zotero_mode": "",
            "zotero_status": "",
            "zotero_import_path": "",
            "zotero_uri": "",
            "zotero_key": "",
            "capture_fidelity": source_fm.get("capture_fidelity", "unknown"),
            "page_state": "llm-enriched",
            "confidence": confidence,
            "compiled": True,
            "manual_notes_present": False,
        }
    else:
        fm = _read_frontmatter(wiki_path)
        if not fm:
            return {"error": f"Could not parse frontmatter for '{citekey}'"}
        fm["confidence"] = confidence
        fm["page_state"] = "llm-enriched"

    # ------------------------------------------------------------------
    # IR write + resolve (only when metadata is provided)
    # ------------------------------------------------------------------
    resolved_ir_path: str | None = None
    ir_warnings: list[str] = []

    if metadata is not None:
        from server.compile_ir import write_ir, resolve_ir  # local import avoids circular dep

        ir_json: dict[str, Any] = {
            "citekey": citekey,
            "title": fm.get("title", ""),
            "authors": fm.get("authors", []),
            "candidate_concepts": metadata.get("candidate_concepts", []),
            "tension_fields": metadata.get("tension_fields", {}),
        }
        for opt_key in ("benchmark_scope", "claimed_novelty", "topics"):
            if opt_key in metadata:
                ir_json[opt_key] = metadata[opt_key]

        write_result = write_ir(vault_path, citekey, ir_json)
        if write_result.get("valid"):
            resolve_result = resolve_ir(vault_path, citekey)
            if "error" not in resolve_result:
                resolved_ir_path = resolve_result["path"]
                LOG.info(
                    "Unified compile: IR resolved for %s → %s",
                    citekey,
                    resolved_ir_path,
                )
            else:
                msg = f"resolve_ir failed: {resolve_result['error']}"
                LOG.warning(msg)
                ir_warnings.append(msg)
        else:
            msg = f"IR validation failed: {write_result.get('errors')}"
            LOG.warning(msg)
            ir_warnings.append(msg)

    # ------------------------------------------------------------------
    authors_raw = fm.get("authors", [])
    if isinstance(authors_raw, list):
        authors_short = ", ".join(str(a) for a in authors_raw[:3])
    else:
        authors_short = str(authors_raw)

    note_payload: dict[str, Any] = {
        "paper": {
            "title": fm.get("title", ""),
            "authors_short": authors_short,
            "year": fm.get("year"),
            "venue": fm.get("venue", ""),
            "citekey": citekey,
            "source_evidence_path": fm.get("source_evidence_path", ""),
            "source_assets_path": fm.get("source_assets_path", ""),
            "zotero_uri": fm.get("zotero_uri", ""),
            "page_state": "llm-enriched",
            "confidence": confidence,
            "why_read": sections["Context"][:300],
            "summary": fm.get("abstract", ""),
            "insights": sections["Discussion"],
            "connections": fm.get("connections", ""),
        },
        "sections": sections,
    }

    wiki_body = build_wiki_paper_body(note_payload)
    result = commit_compile_result(
        vault_path, citekey, "paper", wiki_body, fm, ir_path=resolved_ir_path
    )
    if ir_warnings:
        result["ir_warnings"] = ir_warnings
    return result
