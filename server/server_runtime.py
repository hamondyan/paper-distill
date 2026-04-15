"""Paper Distill MCP Server — runtime helpers and tool implementations.

Business logic lives in focused sub-modules; this file wires them together and
exposes the MCP tool surface (registration is done by *_tools.py via server.py).
"""
from __future__ import annotations

import asyncio
import json
import logging
import re
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from server.arxiv_capture import (
    CleanedArxivDocument,
    bind_paper_to_arxiv,
    capture_arxiv_source,
    clean_ar5iv_html,
)
from server.config import (
    get_env,
    get_paper_distill_settings,
    get_scoring_settings,
    get_topics,
    get_vault_path,
    get_zotero_collection_name,
    get_zotero_local_export_dir,
    get_zotero_mode,
    get_zotero_settings,
)
from server.context_assembler import assemble_runtime_context
from server.obsidian_query import query_library_sync
from server.paper_utils import (
    canonical_html_url,
    canonical_item_url,
    canonical_pdf_url,
    extract_arxiv_id,
    first_author_surname,
    normalize_venue_tier,
    paper_arxiv_id,
    paper_id,
)
from server.research_item import ResearchItem
from server.search import (
    fetch_arxiv_record,
    search_arxiv,
    search_semantic_scholar,
    search_openalex,
    search_dblp,
    search_papers_with_code,
    lookup_unpaywall,
    resolve_crossref,
    dedup_merge,
)
from server.qmd_runtime import ensure_qmd_ready, qmd_get, qmd_ready_report, qmd_search
from server.v3_bootstrap import ensure_v3_layout
from server.v3_ingest import ingest_and_read_v3 as _ingest_and_read_v3
from server.vault_query import query_vault_sync
from server.vault_lint import (
    analyze_knowledge_graph_sync,
    lint_vault_sync,
    vault_stats_sync,
)
from server.vault_ops import (
    append_knowledge_log,
    build_inbox_body,
    build_source_evidence_body,
    citekey_for_paper,
    ensure_vault_structure,
    inbox_note_path,
    mark_inbox_capture_failed,
    mark_inbox_capture_succeeded,
    normalize_knowledge_impact,
    source_evidence_path,
    source_evidence_sidecar_path,
    wiki_paper_path,
    write_json,
    write_markdown,
)
from server.v3_alias import check_concept_alias_v3 as _check_concept_alias_v3
from server.v3_store import upsert_wiki_page_v3 as _upsert_wiki_page_v3
from server.zotero import add_papers as _zotero_add, search_papers as _zotero_search

# ---------------------------------------------------------------------------
# Re-exports from focused sub-modules
# (keeps server.py's _rt.* bindings working without modification)
# ---------------------------------------------------------------------------
from server.paper_scoring import (
    _ACRONYM_MAP,
    _annotate_paper,
    _best_topic_fit,
    _canonical_topics,
    _collapse_text,
    _safe_citations,
    _safe_parse_date,
    _score_author_preference_v2,
    _score_impact_v2,
    _score_keyword_alignment,
    _score_metadata_quality_v2,
    _score_novelty_v2,
    _score_recency_v2,
    _score_rejected_keywords,
    _score_topic_fit,
    _score_venue_tier_v2,
    _tokenize,
)
from server.paper_frontmatter import (
    _DISCOVERY_UPDATE_FIELDS,
    _canonical_url_updates,
    _discover_frontmatter,
    _merge_discovered_paper,
    _prepare_discovered_paper,
    _processed_error,
    _processed_success,
    _source_frontmatter,
    _successful_capture_updates,
)
from server.capture_settings import (
    _capture_method_from_source_doc,
    _capture_options,
    _capture_request_kwargs,
    _capture_settings,
    _relative_to_vault_if_possible,
    _selected_topics,
    _zotero_runtime,
)
from server.paper_identity import (
    _DOI_PATTERN,
    _abs_vault_path,
    _candidate_identifiers,
    _explicit_candidate,
    _existing_paper_ids,
    _extract_doi,
    _extract_abstract_from_text,
    _extract_title_from_text,
    _extract_year_from_text,
    _find_existing_paper,
    _matched_topics_for_explicit_paper,
    _matches_existing_item,
    _source_doc_from_text,
    _source_doc_sidecar_payload,
)
from server.discovery_helpers import (
    _candidate_already_processed,
    _diagnose_discovery_drift,
    _extract_markdown_section,
    _limit_by_diversity,
    _load_candidate_sections,
    _search_query_for_topic,
)
from server.ingestion_helpers import (
    _ingestion_paths,
)

logging.basicConfig(
    format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
    level=logging.INFO,
)
LOG = logging.getLogger("paper-distill")


_MCP_TOOL_SURFACE = {
    "query_library": "query-library",
    "bootstrap_library": "bootstrap-library",
    "source_discover": "source-discover",
    "source_ingest": "source-ingest",
    "wiki_lint": "wiki-lint",
    "library_stats": "library-stats",
    "idea_discover": "idea-discover",
    "idea_tension_signals": "idea-tension-signals",
    "idea_trigger_candidates": "idea-trigger-candidates",
    "paper_distill_extract": "paper-distill-extract",
    "knowledge_compile_resolve": "knowledge-compile-resolve",
    "knowledge_compile_publish": "knowledge-compile-publish",
    "knowledge_compile_status": "knowledge-compile-status",
    "crgp_prepare_context": "crgp-prepare-context",
    "crgp_save_sections": "crgp-save-sections",
}

# Source registry
_SEARCH_SOURCES = {
    "arxiv": search_arxiv,
    "s2": search_semantic_scholar,
    "openalex": search_openalex,
    "dblp": search_dblp,
    "pwc": search_papers_with_code,
}

# Per-source timeout for circuit breaking
_SOURCE_TIMEOUT = 15  # seconds
# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

async def _search_with_timeout(fn, query: str, max_results: int, name: str):
    """Wrap a search coroutine with per-source timeout."""
    try:
        return await asyncio.wait_for(
            fn(query, max_results=max_results), _SOURCE_TIMEOUT
        )
    except asyncio.TimeoutError:
        LOG.warning("Search %s timed out after %ds", name, _SOURCE_TIMEOUT)
        return []
    except Exception as e:
        LOG.warning("Search %s failed: %s", name, e)
        return []









































_CRGP_SECTION_KEYS = (
    "Context", "Related Work", "Gap", "Proposal",
    "Key Results", "Discussion", "Next Steps",
)


def _empty_dnl_note(paper: dict) -> dict:
    """Stub DNL note with empty sections — CRGP content is filled by LLM later."""
    return {
        "paper_id": paper_id(paper),
        "sections": {k: "" for k in _CRGP_SECTION_KEYS},
        "evidence": {},
        "confidence": 0.0,
    }


def kb_search(query: str, scope: str = "canon") -> dict[str, object]:
    vault_path = Path(get_vault_path())
    ensure_v3_layout(vault_path)
    return qmd_search(vault_path=vault_path, query=query, scope=scope)


def kb_get(id_or_path: str) -> dict[str, object]:
    vault_path = Path(get_vault_path())
    ensure_v3_layout(vault_path)
    return qmd_get(vault_path=vault_path, id_or_path=id_or_path)


def v3_status() -> dict[str, object]:
    vault_path = Path(get_vault_path())
    layout = ensure_v3_layout(vault_path)
    try:
        ensure_qmd_ready(vault_path)
    except (FileNotFoundError, subprocess.CalledProcessError):
        pass
    qmd = qmd_ready_report(vault_path)
    return {"layout": layout, "qmd": qmd}


async def discover_papers_v3(query: str | None = None) -> dict[str, Any]:
    """Run the v3 discovery flow that stages inbox stubs and updates seen-cache."""
    from server.v3_discovery import discover_papers_v3 as _discover_papers_v3

    return await _discover_papers_v3(query=query)


async def _prepare_ingestion_candidate(
    candidate: dict,
    vault_path: str,
    collection_name: str,
    appendix_policy: str,
    min_body_chars: int,
    capture_options: dict[str, int | bool] | None = None,
) -> tuple[dict | None, Any | None, str]:
    paper = await _enrich_inbox_candidate(candidate, vault_path=vault_path)
    paper = await bind_paper_to_arxiv(paper) or {}
    if not paper:
        return None, None, "arXiv binding failed during ingestion"

    source_doc = None
    capture_error = ""
    try:
        source_doc = await capture_arxiv_source(
            paper,
            **_capture_request_kwargs(
                appendix_policy,
                min_body_chars,
                capture_options=capture_options,
            ),
        )
        paper["capture_method"] = _capture_method_from_source_doc(source_doc)
    except Exception as exc:
        capture_error = str(exc)
        LOG.warning("ar5iv capture failed for %s, attempting PDF fallback: %s",
                     paper.get("paper_id", ""), capture_error)

    # PDF fallback when ar5iv fails
    if source_doc is None:
        pdf_url = canonical_pdf_url(paper)
        if pdf_url:
            try:
                text = await fetch_pdf_text(pdf_url)
                if not text.startswith("Error"):
                    source_doc = _source_doc_from_text(paper, text, min_body_chars=min_body_chars)
                    paper["capture_method"] = "pdf_text_recovered"
                    LOG.info("PDF fallback succeeded for %s", paper.get("paper_id", ""))
                else:
                    return None, None, f"ar5iv failed ({capture_error}); PDF fallback also failed ({text})"
            except Exception as pdf_exc:
                return None, None, f"ar5iv failed ({capture_error}); PDF fallback also failed ({pdf_exc})"
        else:
            return None, None, f"ar5iv failed ({capture_error}); no PDF URL available for fallback"

    paper["title"] = source_doc.title or paper.get("title", "")
    paper["topic_tags"] = candidate.get("matched_topics", [])
    paper["collection_name"] = collection_name
    paper["venue_source"] = (
        paper.get("venue_source")
        or paper.get("_venue_source")
        or paper.get("source", "")
    )
    return paper, source_doc, ""






async def _write_ingestion_outputs(
    vault_path: str,
    candidate: dict,
    paper: dict,
    source_doc: Any,
    appendix_policy: str,
    zotero_mode: str,
    zotero_status: str,
    zotero_import_path: str,
    zotero_key: str,
    zotero_uri: str,
    dnl_note: dict,
    capture_method: str = "ar5iv_html_cleaned",
) -> tuple[Path, Path, str, str]:
    capture_options = _capture_options()
    capture_method = capture_method or _capture_method_from_source_doc(source_doc)
    capture_fidelity = str(getattr(source_doc, "capture_fidelity", "unknown"))
    capture_source = str(getattr(source_doc, "capture_source", "")).strip()
    figures = list(getattr(source_doc, "figures", []) or [])
    tables = list(getattr(source_doc, "tables", []) or [])
    equations = list(getattr(source_doc, "equations", []) or [])
    (
        citekey,
        source_path,
        source_structured_path,
        wiki_path,
        source_rel_path,
        source_structured_rel_path,
        wiki_rel_path,
    ) = _ingestion_paths(vault_path, paper)
    research_item = ResearchItem.from_search_result(
        paper,
        citekey=citekey,
        topic_tags=list(candidate.get("matched_topics", []) or []),
    )
    await asyncio.to_thread(
        write_markdown,
        source_path,
        _source_frontmatter(
            research_item,
            appendix_policy,
            source_structured_rel_path=source_structured_rel_path,
            capture_method=capture_method,
            capture_fidelity=capture_fidelity,
            capture_source=capture_source,
            figure_count=len(figures),
            table_count=len(tables),
            equation_count=len(equations),
        ),
        build_source_evidence_body(source_doc, source_structured_rel_path),
    )
    if bool(capture_options.get("write_structured_sidecar", True)):
        await asyncio.to_thread(
            write_json,
            source_structured_path,
            _source_doc_sidecar_payload(source_doc),
        )
    return source_path, wiki_path, source_rel_path, wiki_rel_path




























async def _resolve_explicit_paper(identifier: str) -> dict[str, Any]:
    raw = (identifier or "").strip()
    if not raw:
        return {}

    doi = _extract_doi(raw)
    arxiv_id = extract_arxiv_id(raw)
    resolved: dict[str, Any] = {}

    if doi:
        resolved = await resolve_metadata(doi)

    if arxiv_id:
        arxiv_record = await fetch_arxiv_record(arxiv_id)
        if arxiv_record:
            for key, value in arxiv_record.items():
                if value and not resolved.get(key):
                    resolved[key] = value
        resolved["arxiv_id"] = arxiv_id

    if raw.lower().startswith(("http://", "https://")):
        if raw.lower().endswith(".pdf"):
            resolved.setdefault("open_access_url", raw)
        else:
            resolved.setdefault("url", raw)

    if doi:
        resolved["doi"] = doi
    if arxiv_id:
        resolved["arxiv_id"] = arxiv_id

    scoring_settings = get_scoring_settings()
    return _annotate_paper(
        resolved,
        venue_aliases=scoring_settings.get("venue_aliases", {}),
        venue_tiers=scoring_settings.get("venue_tiers", {}),
    )


async def _prepare_direct_add_candidate(
    paper: dict,
    identifier: str,
    appendix_policy: str,
    min_body_chars: int,
    capture_options: dict[str, int | bool] | None = None,
) -> tuple[dict, CleanedArxivDocument | None, str, str]:
    prepared = dict(paper)

    if not prepared.get("arxiv_id") and prepared.get("title") and prepared.get("authors"):
        bound = await bind_paper_to_arxiv(prepared)
        if bound:
            prepared = _annotate_paper(bound)

    if prepared.get("arxiv_id"):
        try:
            source_doc = await capture_arxiv_source(
                prepared,
                **_capture_request_kwargs(
                    appendix_policy,
                    min_body_chars,
                    capture_options=capture_options,
                ),
            )
        except Exception as exc:
            return prepared, None, "", str(exc)
        prepared["title"] = source_doc.title or prepared.get("title", "")
        prepared.setdefault("abstract", source_doc.abstract)
        return _annotate_paper(prepared), source_doc, _capture_method_from_source_doc(source_doc), ""

    pdf_url = canonical_pdf_url(prepared)
    if not pdf_url and identifier.lower().startswith(("http://", "https://")):
        pdf_url = identifier
        prepared.setdefault("open_access_url", identifier)
        prepared["canonical_pdf_url"] = pdf_url

    if not pdf_url:
        return prepared, None, "", "No arXiv ID or fetchable PDF URL available for direct add"

    text = await fetch_pdf_text(pdf_url)
    if text.startswith("Error"):
        return prepared, None, "", text

    try:
        source_doc = _source_doc_from_text(prepared, text, min_body_chars=min_body_chars)
    except Exception as exc:
        return prepared, None, "", str(exc)

    prepared["title"] = prepared.get("title") or source_doc.title
    prepared["abstract"] = prepared.get("abstract") or source_doc.abstract
    prepared["year"] = prepared.get("year") or _extract_year_from_text(text)
    prepared["canonical_pdf_url"] = canonical_pdf_url(prepared) or pdf_url
    prepared["canonical_item_url"] = canonical_item_url(prepared) or pdf_url
    prepared["canonical_html_url"] = canonical_html_url(prepared)
    return _annotate_paper(prepared), source_doc, "pdf_text_recovered", ""




# _ACRONYM_MAP is re-exported from server.paper_scoring (see import block above)






















# ---------------------------------------------------------------------------
# Tool 1: search_papers
# ---------------------------------------------------------------------------

async def search_papers(
    query: str,
    sources: list[str] | None = None,
    max_results: int = 20,
) -> list[dict]:
    """Search academic papers across CS/AI sources.

    Returns deduplicated, merged results enriched with stable paper IDs and
    normalized venue metadata.
    No ranking or filtering applied — the calling AI handles curation.

    Available sources: arxiv, s2 (Semantic Scholar), openalex, dblp, pwc (Papers with Code).

    Args:
        query: Search query string (e.g. "vision language action model")
        sources: List of source keys to search. Defaults to all 5.
        max_results: Maximum results per source (default 20)
    """
    if sources is None:
        sources = list(_SEARCH_SOURCES.keys())

    tasks = []
    source_names = []
    for src in sources:
        fn = _SEARCH_SOURCES.get(src)
        if fn:
            tasks.append(_search_with_timeout(fn, query, max_results, src))
            source_names.append(src)

    if not tasks:
        return []

    results = await asyncio.gather(*tasks)

    all_papers = []
    for name, res in zip(source_names, results):
        if res:
            LOG.info("Search %s: %d results", name, len(res))
            all_papers.extend(res)
        else:
            LOG.info("Search %s: 0 results", name)

    settings = get_paper_distill_settings()
    scoring_settings = get_scoring_settings()
    authority_order = settings.get("venue", {}).get("authority_order", [])
    merged = [
        _annotate_paper(
            paper,
            venue_aliases=scoring_settings.get("venue_aliases", {}),
            venue_tiers=scoring_settings.get("venue_tiers", {}),
        )
        for paper in dedup_merge(all_papers, authority_order=authority_order)
    ]
    LOG.info("Total: %d papers after dedup (from %d candidates)", len(merged), len(all_papers))
    return merged


# ---------------------------------------------------------------------------
# Tool 2: resolve_metadata
# ---------------------------------------------------------------------------

async def resolve_metadata(doi: str) -> dict:
    """Resolve full metadata for a DOI via CrossRef + Unpaywall OA lookup.

    Returns combined metadata including title, authors, year, venue,
    abstract, open_access_url, and more. Useful for enriching papers
    that only have a DOI.

    Args:
        doi: The DOI to resolve (e.g. "10.48550/arxiv.2410.24164")
    """
    crossref_task = resolve_crossref(doi)
    unpaywall_task = lookup_unpaywall(doi)

    crossref_data, unpaywall_data = await asyncio.gather(
        crossref_task, unpaywall_task, return_exceptions=True
    )

    result = {}
    if isinstance(crossref_data, dict):
        result.update(crossref_data)
    elif isinstance(crossref_data, Exception):
        LOG.warning("CrossRef lookup failed for %s: %s", doi, crossref_data)

    if isinstance(unpaywall_data, dict):
        if unpaywall_data.get("best_oa_url"):
            result["open_access_url"] = unpaywall_data["best_oa_url"]
        result["is_oa"] = unpaywall_data.get("is_oa", False)
    elif isinstance(unpaywall_data, Exception):
        LOG.warning("Unpaywall lookup failed for %s: %s", doi, unpaywall_data)

    result["doi"] = doi
    return result


# ---------------------------------------------------------------------------
# Tool 3: zotero_add
# ---------------------------------------------------------------------------

async def zotero_add(papers: list[dict]) -> list[dict]:
    """Add papers to Zotero library with auto-metadata enrichment.

    Dispatches through the configured Zotero mode:
    - ``local_first`` writes local CSL-JSON import packs
    - ``web_api`` creates journal-article items in the remote library
    - ``disabled`` records a skipped handoff

    Args:
        papers: List of paper dicts with at least 'doi' or 'title'.
                Each dict can have: title, authors, year, doi, abstract,
                venue, topic_tags, tldr, citekey.
    """
    zotero_runtime = _zotero_runtime(get_vault_path() or ".")
    mode = zotero_runtime["mode"]
    library_id = zotero_runtime["library_id"]
    api_key = zotero_runtime["api_key"]

    return await _zotero_add(
        papers,
        library_id,
        api_key,
        mode=mode,
        export_dir=zotero_runtime["local_export_dir"],
    )


# ---------------------------------------------------------------------------
# Tool 4: zotero_search
# ---------------------------------------------------------------------------

async def zotero_search(query: str, limit: int = 20) -> list[dict]:
    """Search existing papers in Zotero library.

    Args:
        query: Search query string
        limit: Maximum results (default 20)
    """
    zotero_runtime = _zotero_runtime(get_vault_path() or ".")
    return await _zotero_search(
        query,
        zotero_runtime["library_id"],
        zotero_runtime["api_key"],
        limit=limit,
        mode=zotero_runtime["mode"],
    )


# ---------------------------------------------------------------------------
# Tool 5: fetch_pdf_text (async + ar5iv fallback + noise cleaning)
# ---------------------------------------------------------------------------

def _extract_pdf_sync(pdf_bytes: bytes, max_pages: int) -> str:
    """Synchronous PDF text extraction via PyMuPDF."""
    import fitz  # PyMuPDF

    doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    pages = min(len(doc), max_pages)
    text_parts = [doc[i].get_text() for i in range(pages)]
    doc.close()
    text = "\n\n".join(text_parts)

    # Strip reference section
    ref_pattern = re.compile(
        r"\n(?:References|Bibliography|REFERENCES)\s*\n.*", re.DOTALL
    )
    text = ref_pattern.sub("", text)

    # Strip page headers/footers (lines that are just numbers or very short)
    lines = [
        line
        for line in text.split("\n")
        if len(line.strip()) > 5 or not line.strip().isdigit()
    ]
    return "\n".join(lines)


def _clean_ar5iv_html(html: str) -> str:
    """Extract readable prose from ar5iv HTML using the v2.1 cleaner."""
    return clean_ar5iv_html(html).markdown


def _extract_arxiv_id(url: str) -> str | None:
    """Extract arXiv ID from URL or DOI."""
    # From URL: arxiv.org/abs/2410.24164 or arxiv.org/pdf/2410.24164
    m = re.search(r"arxiv\.org/(?:abs|pdf)/(\d{4}\.\d{4,5}(?:v\d+)?)", url)
    if m:
        return m.group(1)
    # From DOI: 10.48550/arxiv.2410.24164
    m = re.search(r"arxiv\.(\d{4}\.\d{4,5})", url, re.IGNORECASE)
    if m:
        return m.group(1)
    return None


async def fetch_pdf_text(url: str, max_pages: int = 10) -> str:
    """Fetch and extract text from an open-access paper.

    For arXiv papers, tries ar5iv HTML first (faster, cleaner), then falls
    back to PDF. For other URLs, fetches PDF directly.

    Args:
        url: Direct URL to a PDF file, or an arXiv abs/pdf URL
        max_pages: Maximum pages to extract from PDF (default 10)
    """
    import httpx

    arxiv_id = _extract_arxiv_id(url)

    # Try ar5iv HTML first for arXiv papers
    if arxiv_id:
        ar5iv_url = f"https://ar5iv.labs.arxiv.org/html/{arxiv_id}"
        try:
            async with httpx.AsyncClient(timeout=30, follow_redirects=True) as client:
                resp = await client.get(ar5iv_url)
                if resp.status_code == 200:
                    text = await asyncio.to_thread(_clean_ar5iv_html, resp.text)
                    if len(text) > 500:  # sanity check: got meaningful content
                        LOG.info("ar5iv HTML extraction succeeded for %s", arxiv_id)
                        return text
                    LOG.info("ar5iv returned sparse content, falling back to PDF")
        except Exception as e:
            LOG.info("ar5iv failed for %s: %s, falling back to PDF", arxiv_id, e)

    # PDF fallback
    try:
        async with httpx.AsyncClient(timeout=60, follow_redirects=True) as client:
            resp = await client.get(url)
            resp.raise_for_status()
            pdf_bytes = resp.content
    except Exception as e:
        return f"Error fetching PDF: {e}"

    try:
        text = await asyncio.to_thread(_extract_pdf_sync, pdf_bytes, max_pages)
        return text
    except ImportError:
        return "Error: PyMuPDF (fitz) not installed. Add 'pymupdf' to dependencies."
    except Exception as e:
        return f"Error extracting PDF text: {e}"


# ---------------------------------------------------------------------------
# Tool 6: score_papers (v2 topic-aware deterministic formula)
# ---------------------------------------------------------------------------

async def score_papers(
    papers: list[dict],
    topic_keywords: list[str] | None = None,
    known_dois: list[str] | None = None,
    topics: dict | None = None,
    known_ids: list[str] | None = None,
    whitelist_authors: list[str] | None = None,
    preferred_venues: list[str] | None = None,
    venue_aliases: dict | None = None,
    venue_tiers: dict | None = None,
    runtime_context: dict | None = None,
) -> list[dict]:
    """Score papers using the v2 topic-aware deterministic formula."""
    settings = get_paper_distill_settings()
    scoring_settings = settings.get("scoring", {})
    weights = scoring_settings.get("weights", {})
    topics_map = _canonical_topics(topics=topics, topic_keywords=topic_keywords)

    if not topics_map:
        topics_map = _canonical_topics(topics=get_topics())

    aliases = venue_aliases or scoring_settings.get("venue_aliases", {})
    tiers = venue_tiers or scoring_settings.get("venue_tiers", {})
    effective_preferences = dict(runtime_context.get("effective_preferences") or {}) if isinstance(runtime_context, dict) else {}
    settings_preferences = settings.get("research_profile", {}).get("learned_preferences", {})
    preferred_venues = preferred_venues or effective_preferences.get("preferred_venues") or settings_preferences.get(
        "preferred_venues", []
    )
    whitelist_authors = whitelist_authors or effective_preferences.get("whitelist_authors") or settings.get(
        "research_profile", {}
    ).get("whitelist_authors", [])
    rejected_keywords = effective_preferences.get("rejected_keywords") or settings_preferences.get(
        "rejected_keywords", []
    )
    profile_terms = effective_preferences.get("profile_terms") or []
    taste_terms = effective_preferences.get("taste_terms") or []

    known_id_set = {item.strip().lower() for item in (known_ids or []) if item}
    known_id_set.update(
        f"doi:{doi.strip().lower()}" for doi in (known_dois or []) if doi
    )
    scored = []

    for p in papers:
        annotated = _annotate_paper(p, venue_aliases=aliases, venue_tiers=tiers)
        best_topic, topic_fit = _best_topic_fit(annotated, topics_map)
        rec = _score_recency_v2(annotated)
        nov = _score_novelty_v2(annotated, known_id_set)
        imp = _score_impact_v2(annotated)
        venue_score = _score_venue_tier_v2(annotated)
        author_pref = _score_author_preference_v2(
            annotated,
            whitelist_authors=whitelist_authors,
            preferred_venues=preferred_venues,
        )
        metadata_quality = _score_metadata_quality_v2(annotated)
        rejected_penalty = _score_rejected_keywords(annotated, rejected_keywords)
        profile_alignment = _score_keyword_alignment(annotated, profile_terms)
        taste_alignment = _score_keyword_alignment(annotated, taste_terms)

        total = (
            weights.get("topic_fit", 0.40) * topic_fit
            + weights.get("recency", 0.20) * rec
            + weights.get("novelty", 0.15) * nov
            + weights.get("impact", 0.10) * imp
            + weights.get("venue_tier", 0.07) * venue_score
            + weights.get("author_preference", 0.05) * author_pref
            + weights.get("metadata_quality", 0.03) * metadata_quality
            + weights.get("profile_alignment", 0.05) * profile_alignment
            + weights.get("taste_alignment", 0.03) * taste_alignment
            + rejected_penalty
        )

        scored_paper = dict(annotated)
        scored_paper["best_topic"] = best_topic
        scored_paper["_score"] = round(total, 4)
        scored_paper["_score_breakdown"] = {
            "topic_fit": round(topic_fit, 4),
            "recency": round(rec, 4),
            "novelty": round(nov, 4),
            "impact": round(imp, 4),
            "venue_tier": round(venue_score, 4),
            "author_preference": round(author_pref, 4),
            "metadata_quality": round(metadata_quality, 4),
            "profile_alignment": round(profile_alignment, 4),
            "taste_alignment": round(taste_alignment, 4),
            "rejected_penalty": round(rejected_penalty, 4),
        }
        scored.append(scored_paper)

    scored.sort(
        key=lambda x: (
            x["_score"],
            x["_score_breakdown"].get("topic_fit", 0),
            x["_score_breakdown"].get("venue_tier", 0),
            x.get("year") or 0,
        ),
        reverse=True,
    )
    return scored


# ---------------------------------------------------------------------------
# Tool 7: query-library (AI's interface to library state)
# ---------------------------------------------------------------------------

async def query_vault(
    section: str = "all",
    topic: str | None = None,
    uncompiled_only: bool = False,
    status: str | None = None,
    detail: str = "compact",
    limit: int | None = None,
    sort_by: str = "updated_at",
    days_back: int | None = None,
) -> dict:
    """Query the Paper Distill library metadata by parsing YAML frontmatter.

    This is the AI's interface to library state. Use this instead of reading
    _index.md files (which are human landing notes, not actual data).

    Args:
        section: "inbox", "source_evidence", "sources", "papers", "concepts",
            "methods", "topics", or "all"
        topic: Filter by topic tag (optional)
        uncompiled_only: If True, only return source evidence not yet compiled
        status: Filter inbox notes by status (optional).
            Status values:
              - proposed: AI-discovered, awaiting human review
              - approved: human-approved, ready for ingestion
              - rejected: human-rejected, will not be processed
              - deferred: postponed for later review
              - failed: capture attempted but errored
        detail: "compact" (default) strips heavy text fields (abstract,
            summary, why_recommended) and adds a short preview_text;
            "full" returns all frontmatter fields as-is.
        limit: Maximum number of items to return per section.
        sort_by: Field to sort by ("updated_at", "retrieved_at", "_mtime").
            The default "updated_at" falls back to the best available
            timestamp when a section does not store updated_at explicitly.
        days_back: Only return items modified/updated within this many days.

    Returns:
        Dict with "stats" (per-section counts) and "sections" (per-section
        item lists with frontmatter metadata).
    """
    vault_path = get_vault_path()
    if not vault_path:
        return {"error": "VAULT_PATH not configured. Set it in settings.json or env."}

    result = await asyncio.to_thread(
        query_library_sync,
        vault_path,
        section,
        topic,
        uncompiled_only,
        status,
        detail,
        limit,
        sort_by,
        days_back,
    )
    result["runtime_context"] = await asyncio.to_thread(
        assemble_runtime_context,
        vault_path,
        task="query",
        query_text=" ".join(part for part in [section, topic or ""] if part).strip(),
        topic_keys=[topic] if topic else None,
    )
    return result


# ---------------------------------------------------------------------------
# Tool 8: bootstrap_vault
# ---------------------------------------------------------------------------

async def bootstrap_vault(vault_path: str | None = None) -> dict:
    """Initialize the Paper Distill directory structure inside an Obsidian vault."""
    target = vault_path or get_vault_path()
    if not target:
        return {"error": "VAULT_PATH not configured. Set it in settings.json or env."}

    root = await asyncio.to_thread(ensure_vault_structure, target)
    return {
        "vault_path": target,
        "paper_distill_root": str(root),
    }










async def _enrich_inbox_candidate(candidate: dict, vault_path: str | None = None) -> dict:
    enriched = dict(candidate)
    if not enriched.get("venue") and enriched.get("venue_raw"):
        enriched["venue"] = enriched.get("venue_raw")

    note_rel_path = str(enriched.get("_path", "")).strip()
    if vault_path and note_rel_path:
        note_sections = _load_candidate_sections(vault_path, note_rel_path)
        for field in (
            "summary",
            "abstract",
            "why_recommended",
            "open_access_url",
            "canonical_pdf_url",
            "canonical_html_url",
        ):
            if note_sections.get(field) and not enriched.get(field):
                enriched[field] = note_sections[field]

    doi = str(enriched.get("doi", "")).strip()
    needs_metadata = any(
        not enriched.get(field)
        for field in ("abstract", "open_access_url")
    )
    if doi and needs_metadata:
        resolved = await resolve_metadata(doi)
        if isinstance(resolved, dict):
            for field in (
                "title",
                "authors",
                "year",
                "venue",
                "abstract",
                "open_access_url",
            ):
                if resolved.get(field) and not enriched.get(field):
                    enriched[field] = resolved.get(field)

    scoring_settings = get_scoring_settings()
    return _annotate_paper(
        enriched,
        venue_aliases=scoring_settings.get("venue_aliases", {}),
        venue_tiers=scoring_settings.get("venue_tiers", {}),
    )




# ---------------------------------------------------------------------------
# Tool 9: source-discover
# ---------------------------------------------------------------------------



async def discover_papers(
    query: str | None = None,
    topic_keys: list[str] | None = None,
    max_results_per_source: int | None = None,
    save_to_inbox: bool = True,
) -> dict:
    """Search, score, arXiv-bind, and optionally save candidate papers into inbox notes."""
    settings = get_paper_distill_settings()
    selected_topics = _selected_topics(query, topic_keys)

    if not selected_topics:
        return {"error": "No topics available for discovery."}

    vault_path = get_vault_path()
    if save_to_inbox and not vault_path:
        return {"error": "VAULT_PATH not configured. Set it in settings.json or env."}

    if save_to_inbox:
        await asyncio.to_thread(ensure_vault_structure, vault_path)

    search_sources = settings.get("search", {}).get("sources", list(_SEARCH_SOURCES.keys()))
    max_per_source = max_results_per_source or settings.get("search", {}).get("max_per_topic", 20)
    max_candidates = settings.get("workflow", {}).get("max_candidates_per_topic", 5)
    diversity_cap = settings.get("workflow", {}).get("diversity_cap_per_cluster", 2)
    require_arxiv_binding = settings.get("workflow", {}).get("require_arxiv_binding", True)
    known_ids = _existing_paper_ids(vault_path) if vault_path else set()
    existing_in_vault_ids = set(known_ids)
    runtime_context = assemble_runtime_context(
        vault_path,
        task="discovery",
        query_text=query,
        topic_keys=list(selected_topics.keys()),
    )

    discovered: list[dict] = []
    discovered_by_id: dict[str, dict] = {}
    written: list[str] = []

    for topic_key, topic in selected_topics.items():
        search_query = query or _search_query_for_topic(topic_key, topic)

        # Bounded 2-pass exploration
        for pass_num in range(2):
            results = await search_papers(
                query=search_query,
                sources=search_sources,
                max_results=max_per_source,
            )
            scored = await score_papers(
                papers=results,
                topics={topic_key: topic},
                known_ids=sorted(known_ids),
                runtime_context=runtime_context,
            )

            # After pass 1, diagnose drift and decide whether to refine
            if pass_num == 0 and len(scored) >= 3:
                drift = _diagnose_discovery_drift(scored, topic)
                if drift.get("drifted"):
                    exclude_terms = drift.get("exclude_terms", [])
                    if exclude_terms:
                        refined_parts = search_query.split()
                        refined_parts.extend(f"-{t}" for t in exclude_terms)
                        search_query = " ".join(refined_parts)
                        LOG.info(
                            "Discovery drift detected for %s (coverage=%.0f%%, off_topic=%.0f%%), "
                            "refining query with excludes: %s",
                            topic_key,
                            drift.get("keyword_coverage", 0) * 100,
                            drift.get("off_topic_venue_ratio", 0) * 100,
                            exclude_terms,
                        )
                        continue  # go to pass 2
                break  # no drift, skip pass 2

            if pass_num == 1:
                break  # always stop after pass 2

        capped = _limit_by_diversity(scored, diversity_cap)[:max_candidates]
        for paper in capped:
            bound = await bind_paper_to_arxiv(paper) if require_arxiv_binding else dict(paper)
            if require_arxiv_binding and not bound:
                continue
            if not bound:
                continue
            pid = str(bound.get("paper_id", "")).lower()
            if not pid:
                continue
            if pid in existing_in_vault_ids:
                continue

            if pid in discovered_by_id:
                _merge_discovered_paper(discovered_by_id[pid], bound, topic_key)
                continue

            prepared = _prepare_discovered_paper(bound, topic_key, topic)
            discovered.append(prepared)
            discovered_by_id[pid] = prepared

    for paper in discovered:
        pid = str(paper.get("paper_id", "")).lower()
        if not pid:
            continue
        known_ids.add(pid)
        if save_to_inbox:
            note_path = await asyncio.to_thread(inbox_note_path, vault_path, paper)
            await asyncio.to_thread(
                write_markdown,
                note_path,
                _discover_frontmatter(paper),
                build_inbox_body(paper),
            )
            written.append(str(note_path))

    return {
        "topics": list(selected_topics.keys()),
        "papers": discovered,
        "written": written,
        "runtime_context": runtime_context,
    }


# ---------------------------------------------------------------------------
# Tool 10: ingest_and_read
# ---------------------------------------------------------------------------

async def ingest_and_read_v3(input_value: str) -> dict:
    """Ingest approved inbox notes or a direct paper URL into raw/evidence."""
    return await _ingest_and_read_v3(input_value=input_value)


# ---------------------------------------------------------------------------
# Tool 11: source-ingest
# ---------------------------------------------------------------------------

async def source_ingest(
    mode: str = "approved_inbox",
    identifier: str = "",
    status: str = "approved",
    limit: int = 20,
    collection_name: str = "",
    topic_keys: list[str] | None = None,
) -> dict:
    """Persist approved evidence into the `sources/` truth layer.

    Args:
        mode: `"approved_inbox"` ingests approved inbox notes;
            `"direct_identifier"` resolves one DOI/arXiv/URL directly.
        identifier: Required when `mode="direct_identifier"`.
        status: Inbox status filter used by `approved_inbox` mode.
        limit: Maximum number of inbox candidates to ingest.
        collection_name: Optional Zotero collection override.
        topic_keys: Optional topic tags for `direct_identifier` mode.
    """
    if mode == "approved_inbox":
        if identifier.strip():
            return {
                "error": "identifier is only valid when mode='direct_identifier'."
            }
        return await process_inbox(
            status=status,
            limit=limit,
            collection_name=collection_name,
        )

    if mode == "direct_identifier":
        if not identifier.strip():
            return {
                "error": "identifier is required when mode='direct_identifier'."
            }
        return await add_paper(
            identifier,
            topic_keys=topic_keys,
            collection_name=collection_name,
        )

    return {
        "error": (
            "Invalid mode. Must be 'approved_inbox' or 'direct_identifier'."
        )
    }


# Internal source-ingest helpers
# ---------------------------------------------------------------------------

async def process_inbox(
    status: str = "approved",
    limit: int = 20,
    collection_name: str = "",
) -> dict:
    """Capture approved inbox notes into source/note layers, then hand off to Zotero."""
    vault_path = get_vault_path()
    if not vault_path:
        return {"error": "VAULT_PATH not configured. Set it in settings.json or env."}

    zotero_runtime = _zotero_runtime(vault_path)
    collection = collection_name or zotero_runtime["collection_name"]
    if zotero_runtime["mode"] == "web_api" and (
        not zotero_runtime["library_id"] or not zotero_runtime["api_key"]
    ):
        return {"error": "ZOTERO_LIBRARY_ID and ZOTERO_API_KEY required for web_api mode"}

    appendix_policy, min_body_chars = _capture_settings()
    capture_options = _capture_options()

    ensure_vault_structure(vault_path)
    inbox = query_vault_sync(vault_path, section="inbox", status=status, detail="full")
    candidates = inbox.get("sections", {}).get("inbox", [])[:limit]
    existing_raw_ids = _existing_paper_ids(vault_path, sections=("source_evidence", "papers"))
    processed: list[dict] = []
    created_pages: list[str] = []
    updated_pages: list[str] = []
    conflicts_or_skips: list[str] = []
    processed_titles: list[str] = []

    for candidate in candidates:
        pid = str(candidate.get("paper_id", "")).lower()
        if _candidate_already_processed(candidate, existing_raw_ids):
            continue

        inbox_note_abs = Path(vault_path) / candidate["_path"]
        paper, source_doc, error = await _prepare_ingestion_candidate(
            candidate,
            vault_path,
            collection,
            appendix_policy,
            min_body_chars,
            capture_options=capture_options,
        )
        if error:
            await asyncio.to_thread(
                mark_inbox_capture_failed,
                inbox_note_abs,
                error=error,
                canonical_html_url=(paper or {}).get("canonical_html_url", ""),
                canonical_pdf_url=(paper or {}).get("canonical_pdf_url", ""),
            )
            processed.append(_processed_error(candidate, error))
            conflicts_or_skips.append(f"{candidate.get('paper_id', '')}: {error}")
            continue

        dnl_note = _empty_dnl_note(paper)
        paper["citekey"] = citekey_for_paper(paper)
        zotero_items = await _zotero_add(
            [paper],
            zotero_runtime["library_id"],
            zotero_runtime["api_key"],
            mode=zotero_runtime["mode"],
            export_dir=zotero_runtime["local_export_dir"],
        )
        if not zotero_items or zotero_items[0].get("error"):
            error_text = zotero_items[0].get("error", "Zotero add failed") if zotero_items else "Zotero add failed"
            await asyncio.to_thread(
                mark_inbox_capture_failed,
                inbox_note_abs,
                error=error_text,
                canonical_html_url=paper.get("canonical_html_url", ""),
                canonical_pdf_url=paper.get("canonical_pdf_url", ""),
            )
            processed.append(_processed_error(candidate, error_text))
            continue

        zotero_item = zotero_items[0]
        zotero_key = zotero_item.get("key", "")
        zotero_uri = zotero_item.get("zotero_uri", "")
        zotero_mode = zotero_item.get("zotero_mode", zotero_runtime["mode"])
        zotero_status = zotero_item.get("zotero_status", "cloud_synced" if zotero_uri else "")
        zotero_import_path = _relative_to_vault_if_possible(
            vault_path,
            zotero_item.get("zotero_import_path", ""),
        )
        source_path, wiki_path, source_rel_path, wiki_rel_path = await _write_ingestion_outputs(
            vault_path,
            candidate,
            paper,
            source_doc,
            appendix_policy,
            zotero_mode,
            zotero_status,
            zotero_import_path,
            zotero_key,
            zotero_uri,
            dnl_note,
            capture_method=paper.get("capture_method", "ar5iv_html_cleaned"),
        )

        await asyncio.to_thread(
            mark_inbox_capture_succeeded,
            inbox_note_abs,
            _successful_capture_updates(
                wiki_rel_path,
                source_rel_path,
                source_rel_path.replace(".md", ".assets.json"),
                paper,
                zotero_mode,
                zotero_status,
                zotero_import_path,
                zotero_key,
                zotero_uri,
            ),
        )
        existing_raw_ids.add(pid)
        created_pages.extend([source_rel_path])
        updated_pages.append(str(candidate.get("_path", "")))
        processed_titles.append(str(candidate.get("title", "")).strip() or candidate.get("paper_id", "paper"))
        processed.append(
            _processed_success(
                candidate,
                zotero_mode,
                zotero_status,
                zotero_import_path,
                zotero_key,
                zotero_uri,
                source_path,
                wiki_path,
            )
        )
    impact = normalize_knowledge_impact(
        {
            "created_pages": created_pages,
            "updated_pages": updated_pages,
            "conflicts_or_skips": conflicts_or_skips,
        }
    )
    if processed:
        append_knowledge_log(
            vault_path,
            event_type="source-ingest",
            title=", ".join(title for title in processed_titles if title) or f"{len(processed)} inbox papers",
            summary=f"Processed {len(processed)} approved inbox item(s) into the maintained knowledge base.",
            impact=impact,
        )

    return {"processed": processed, "knowledge_impact": impact}


# ---------------------------------------------------------------------------
# Internal direct-ingest helper
# ---------------------------------------------------------------------------

async def add_paper(
    identifier: str,
    topic_keys: list[str] | None = None,
    collection_name: str = "",
) -> dict:
    """Directly add one explicit paper into source evidence.

    Accepts a DOI, arXiv identifier, arXiv URL, DOI URL, or direct PDF URL.
    Unlike discovery, this bypasses inbox because the paper is already
    user-approved. The wiki/papers page is created later by the compile step.
    """
    vault_path = get_vault_path()
    if not vault_path:
        return {"error": "VAULT_PATH not configured. Set it in settings.json or env."}

    zotero_runtime = _zotero_runtime(vault_path)
    if zotero_runtime["mode"] == "web_api" and (
        not zotero_runtime["library_id"] or not zotero_runtime["api_key"]
    ):
        return {"error": "ZOTERO_LIBRARY_ID and ZOTERO_API_KEY required for web_api mode"}

    if not identifier.strip():
        return {"error": "identifier is required"}

    ensure_vault_structure(vault_path)
    appendix_policy, min_body_chars = _capture_settings()
    capture_options = _capture_options()

    paper = await _resolve_explicit_paper(identifier)
    if not paper:
        return {"error": "Could not resolve metadata from the provided identifier"}

    existing = _find_existing_paper(vault_path, paper)
    if existing:
        return {
            "added": False,
            "existing": True,
            "knowledge_impact": normalize_knowledge_impact(),
            **existing,
        }

    matched_topics = _matched_topics_for_explicit_paper(paper, topic_keys)
    candidate = _explicit_candidate(paper, matched_topics)

    paper["topic_tags"] = matched_topics
    paper["collection_name"] = collection_name or zotero_runtime["collection_name"]
    paper["venue_source"] = (
        paper.get("venue_source")
        or paper.get("_venue_source")
        or paper.get("source", "")
    )

    paper, source_doc, capture_method, capture_error = await _prepare_direct_add_candidate(
        paper,
        identifier,
        appendix_policy,
        min_body_chars,
        capture_options=capture_options,
    )
    if capture_error or source_doc is None:
        return {
            "added": False,
            "existing": False,
            "paper_id": paper.get("paper_id", ""),
            "title": paper.get("title", ""),
            "error": capture_error or "Capture failed",
            "knowledge_impact": normalize_knowledge_impact(
                {"conflicts_or_skips": [capture_error or "Capture failed"]}
            ),
        }

    candidate["paper_id"] = paper.get("paper_id", candidate.get("paper_id", ""))
    dnl_note = _empty_dnl_note(paper)
    paper["citekey"] = citekey_for_paper(paper)

    zotero_key = ""
    zotero_uri = ""
    zotero_status = "disabled" if zotero_runtime["mode"] == "disabled" else "not_attempted"
    zotero_mode = zotero_runtime["mode"]
    zotero_import_path = ""
    zotero_warning = ""

    zotero_items = await _zotero_add(
        [paper],
        zotero_runtime["library_id"],
        zotero_runtime["api_key"],
        mode=zotero_runtime["mode"],
        export_dir=zotero_runtime["local_export_dir"],
    )
    if zotero_items and not zotero_items[0].get("error"):
        zotero_item = zotero_items[0]
        zotero_key = zotero_item.get("key", "")
        zotero_uri = zotero_item.get("zotero_uri", "")
        zotero_mode = zotero_item.get("zotero_mode", zotero_mode)
        zotero_status = zotero_item.get("zotero_status", zotero_status)
        zotero_import_path = _relative_to_vault_if_possible(
            vault_path,
            zotero_item.get("zotero_import_path", ""),
        )
    elif zotero_items:
        zotero_warning = zotero_items[0].get("error", "Zotero add failed")
        zotero_status = "error"

    source_path, wiki_path, source_rel_path, wiki_rel_path = await _write_ingestion_outputs(
        vault_path,
        candidate,
        paper,
        source_doc,
        appendix_policy,
        zotero_mode,
        zotero_status,
        zotero_import_path,
        zotero_key,
        zotero_uri,
        dnl_note,
        capture_method=capture_method,
    )

    impact = normalize_knowledge_impact(
        {
            "created_pages": [source_rel_path],
            "conflicts_or_skips": [zotero_warning] if zotero_warning else [],
        }
    )
    append_knowledge_log(
        vault_path,
        event_type="source-ingest",
        title=paper.get("title", "") or paper.get("paper_id", "paper"),
        summary="Added a user-approved paper into sources/evidence. Run /compile to generate the wiki page.",
        impact=impact,
    )

    return {
        "added": True,
        "existing": False,
        "paper_id": paper.get("paper_id", ""),
        "title": paper.get("title", ""),
        "matched_topics": matched_topics,
        "capture_fidelity": str(getattr(source_doc, "capture_fidelity", "unknown")),
        "zotero_mode": zotero_mode,
        "zotero_status": zotero_status,
        "zotero_import_path": zotero_import_path,
        "zotero_key": zotero_key,
        "zotero_uri": zotero_uri,
        "source_evidence_abs_path": str(source_path),
        "wiki_paper_abs_path": str(wiki_path),
        "source_evidence_path": source_rel_path,
        "source_assets_path": source_rel_path.replace(".md", ".assets.json"),
        "wiki_paper_path": wiki_rel_path,
        "page_state": "auto",
        "warning": zotero_warning,
        "knowledge_impact": impact,
    }


# ---------------------------------------------------------------------------
# Tool 11: wiki-lint
# ---------------------------------------------------------------------------

async def lint_vault() -> dict:
    """Run deterministic structural health checks on the vault.

    Checks for: orphaned articles, broken backlinks, missing frontmatter,
    stale indexes, uncompiled papers, and missing concept stubs.
    Returns a structured JSON report with counts and file lists.
    """
    vault_path = get_vault_path()
    if not vault_path:
        return {"error": "VAULT_PATH not configured."}
    return await asyncio.to_thread(lint_vault_sync, vault_path)


# ---------------------------------------------------------------------------
# Tool 12: library-stats
# ---------------------------------------------------------------------------

async def vault_stats() -> dict:
    """Compute vault statistics: paper counts per stage, compilation rate,
    wiki article counts, per-topic breakdowns, and last activity timestamp.
    """
    vault_path = get_vault_path()
    if not vault_path:
        return {"error": "VAULT_PATH not configured."}
    return await asyncio.to_thread(vault_stats_sync, vault_path)


# ---------------------------------------------------------------------------
# Tool 13: idea-discover
# ---------------------------------------------------------------------------

async def analyze_knowledge_graph(user_topics: list[str] | None = None) -> dict:
    """Analyze the vault's concept-paper graph to find structural research gaps.

    Returns condensed gap lists (methodology mismatches, combination
    opportunities, recurring problems, scaling questions) that can be
    turned into qualitative research ideas by the LLM.

    Args:
        user_topics: The user's research topics for mismatch analysis.
                     If omitted, reads from settings.json.
    """
    vault_path = get_vault_path()
    if not vault_path:
        return {"error": "VAULT_PATH not configured."}
    if user_topics is None:
        topics_config = get_topics()
        if isinstance(topics_config, dict):
            user_topics = [key for key in topics_config.keys() if str(key).strip()]
        else:
            user_topics = [
                str(t.get("key", t.get("name", ""))).strip()
                for t in topics_config
                if isinstance(t, dict) and str(t.get("key", t.get("name", ""))).strip()
            ]
    result = await asyncio.to_thread(analyze_knowledge_graph_sync, vault_path, user_topics)
    result["runtime_context"] = await asyncio.to_thread(
        assemble_runtime_context,
        vault_path,
        task="idea_generation",
        topic_keys=user_topics,
        user_topics=user_topics,
    )
    result["local_memory_evidence"] = list(
        result["runtime_context"].get("memory", {}).get("local_evidence", [])
    )
    return result


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

# ---------------------------------------------------------------------------
# Tool 15: update_learned_preferences
# ---------------------------------------------------------------------------

async def update_learned_preferences(
    accepted_keywords: list[str] | None = None,
    rejected_keywords: list[str] | None = None,
    preferred_venues: list[str] | None = None,
) -> dict:
    """Safely update the user's learned preferences in settings.json.

    Atomically appends new items to existing lists without overwriting.
    Validates schema before writing.

    Args:
        accepted_keywords: Keywords to add to accepted list.
        rejected_keywords: Keywords to add to rejected list.
        preferred_venues: Venues to add to preferred list.
    """
    from server.config import _settings_path

    settings_path = _settings_path()
    if not settings_path.exists():
        return {"error": "settings.json not found"}

    try:
        with settings_path.open("r", encoding="utf-8") as f:
            settings = json.load(f)
    except (OSError, json.JSONDecodeError) as exc:
        return {"error": f"Failed to read settings.json: {exc}"}

    prefs = (
        settings.setdefault("paper_distill", {})
        .setdefault("research_profile", {})
        .setdefault("learned_preferences", {})
    )

    added = {}
    for field, new_items in [
        ("accepted_keywords", accepted_keywords),
        ("rejected_keywords", rejected_keywords),
        ("preferred_venues", preferred_venues),
    ]:
        if not new_items:
            continue
        existing = prefs.setdefault(field, [])
        if not isinstance(existing, list):
            existing = []
            prefs[field] = existing
        new_unique = [item for item in new_items if item not in existing]
        existing.extend(new_unique)
        added[field] = new_unique

    prefs["feedback_count"] = prefs.get("feedback_count", 0) + 1

    try:
        with settings_path.open("w", encoding="utf-8") as f:
            json.dump(settings, f, indent=2, ensure_ascii=False)
            f.write("\n")
    except OSError as exc:
        return {"error": f"Failed to write settings.json: {exc}"}

    # Clear cached settings so next read picks up new data
    from server.config import load_settings
    load_settings.cache_clear()

    return {"updated": True, "added": added}


# ---------------------------------------------------------------------------
# Tool 16: upsert_wiki_article
# ---------------------------------------------------------------------------

async def upsert_wiki_article(
    citekey: str,
    section: str,
    content: str,
    frontmatter: dict | None = None,
) -> dict:
    """Create or update a wiki article with path safety guards.

    This is the safe, intent-based API for wiki writes. It validates paths
    to prevent directory traversal and ensures frontmatter schema compliance.

    Args:
        citekey: Basename for the article file (e.g. "brohan2023rt2").
        section: Wiki section — "papers", "concepts", or "methods".
        content: Full markdown body content for the article.
        frontmatter: Optional YAML frontmatter dict to merge/set.
    """
    if section not in ("papers", "concepts", "methods"):
        return {"error": f"Invalid section: {section}. Must be papers, concepts, or methods."}

    # Path safety: reject traversal attempts
    if ".." in citekey or "/" in citekey or "\\" in citekey:
        return {"error": "Invalid citekey — must not contain path separators or '..'"}

    vault_path = get_vault_path()
    if not vault_path:
        return {"error": "VAULT_PATH not configured."}

    target_dir = Path(vault_path) / "Paper Distill" / "wiki" / section
    target_dir.mkdir(parents=True, exist_ok=True)
    target_file = target_dir / f"{citekey}.md"

    frontmatter_payload = dict(frontmatter or {})
    if section == "papers":
        frontmatter_payload.setdefault("citekey", citekey)
    elif section == "concepts":
        frontmatter_payload.setdefault("concept", citekey)
    elif section == "methods":
        frontmatter_payload.setdefault("method", citekey)

    required_frontmatter = {
        "papers": ("citekey", "title"),
        "concepts": ("concept",),
        "methods": (),
    }
    missing_fields = [
        field
        for field in required_frontmatter[section]
        if not str(frontmatter_payload.get(field, "")).strip()
    ]
    if missing_fields:
        return {
            "error": (
                f"Missing required frontmatter for {section}: "
                + ", ".join(missing_fields)
            )
        }

    # Build markdown with validated frontmatter
    lines = []
    if frontmatter_payload:
        import yaml
        lines.append("---")
        lines.append(
            yaml.dump(
                frontmatter_payload,
                default_flow_style=False,
                allow_unicode=True,
                sort_keys=False,
            ).strip()
        )
        lines.append("---")
        lines.append("")
    lines.append(content)

    await asyncio.to_thread(target_file.write_text, "\n".join(lines), "utf-8")

    return {
        "written": True,
        "path": str(target_file),
        "relative_path": f"Paper Distill/wiki/{section}/{citekey}.md",
    }


# ---------------------------------------------------------------------------
# Tool 16b: upsert_wiki_page (v3 cutover)
# ---------------------------------------------------------------------------

async def upsert_wiki_page_v3(
    page_type: str,
    target: str,
    frontmatter: dict,
    body: str,
) -> dict:
    vault_path = get_vault_path()
    if not vault_path:
        return {"ok": False, "error": "VAULT_PATH not configured.", "warnings": []}
    return _upsert_wiki_page_v3(Path(vault_path), page_type, target, frontmatter, body)


# ---------------------------------------------------------------------------
# Tool 17: register_concept
# ---------------------------------------------------------------------------

async def register_concept_tool(
    canonical: str,
    concept_type: str = "concept",
    aliases: list[str] | None = None,
) -> dict:
    """Register a concept in the Canonical Registry.

    If the slug already exists, returns the existing entry.  If an alias
    matches an existing concept and auto-merge conditions are met (slug
    match, abbreviation whitelist, or spelling variant), the concept is
    automatically merged.

    Args:
        canonical: Display name (e.g. "Diffusion Policy").
        concept_type: One of "concept", "method", "topic".
        aliases: Additional surface forms to register.
    """
    vault_path = get_vault_path()
    if not vault_path:
        return {"error": "VAULT_PATH not configured."}

    from server.concept_registry import register_concept
    return await asyncio.to_thread(
        register_concept, vault_path, canonical, concept_type, aliases,
    )


# ---------------------------------------------------------------------------
# Tool 18: resolve_concept
# ---------------------------------------------------------------------------

async def resolve_concept_tool(surface_form: str) -> dict:
    """Resolve a surface form to its canonical concept in the registry.

    Tries alias match, slug match, then abbreviation expansion.
    Returns the canonical concept info or null if not found.

    Args:
        surface_form: The name to look up (e.g. "VLA", "diffusion policy").
    """
    vault_path = get_vault_path()
    if not vault_path:
        return {"error": "VAULT_PATH not configured."}

    from server.concept_registry import resolve_concept
    result = await asyncio.to_thread(resolve_concept, vault_path, surface_form)
    return result or {"resolved": False, "surface_form": surface_form}


# ---------------------------------------------------------------------------
# Tool 19: merge_concepts
# ---------------------------------------------------------------------------

async def merge_concepts_tool(
    from_id: str,
    to_id: str,
    reason: str = "",
) -> dict:
    """Merge one concept into another in the registry.

    All aliases of the source concept are re-mapped to the target.
    Paper counts are combined.  The merge is recorded in history
    for traceability.

    Args:
        from_id: Slug of the concept to merge away.
        to_id: Slug of the target concept to merge into.
        reason: Human-readable reason for the merge.
    """
    vault_path = get_vault_path()
    if not vault_path:
        return {"error": "VAULT_PATH not configured."}

    from server.concept_registry import merge_concepts
    return await asyncio.to_thread(
        merge_concepts, vault_path, from_id, to_id, reason,
    )


# ---------------------------------------------------------------------------
# Tool 19b: check_concept_alias (v3 cutover)
# ---------------------------------------------------------------------------

async def check_concept_alias_v3(name: str) -> dict:
    vault_path = get_vault_path()
    if not vault_path:
        return {"exists": False, "canonical": name, "error": "VAULT_PATH not configured."}
    return _check_concept_alias_v3(Path(vault_path), name)


# ---------------------------------------------------------------------------
# Tool 20: list_concepts
# ---------------------------------------------------------------------------

async def list_concepts_tool(
    concept_type: str | None = None,
    min_paper_count: int = 0,
) -> list[dict]:
    """List concepts from the Canonical Registry.

    Args:
        concept_type: Filter by type — "concept", "method", or "topic".
        min_paper_count: Only return concepts with at least this many papers.
    """
    vault_path = get_vault_path()
    if not vault_path:
        return [{"error": "VAULT_PATH not configured."}]

    from server.concept_registry import list_concepts
    return await asyncio.to_thread(
        list_concepts, vault_path, concept_type, min_paper_count,
    )


# ---------------------------------------------------------------------------
# Tool 21: reconcile_maintenance
# ---------------------------------------------------------------------------

async def reconcile_maintenance(auto_confirm: bool = True) -> dict:
    """Run lint + stats, then generate deduplicated maintenance tasks.

    This is the bridge between pure-read analysis (wiki-lint, library-stats)
    and the actionable maintenance queue.  Lint results are compared against
    existing pending tasks to avoid duplicates.

    Tasks that meet auto-confirm criteria (the three safe merge rules:
    slug match, abbreviation whitelist, spelling variant) are automatically
    confirmed.

    Args:
        auto_confirm: Auto-confirm eligible tasks (default True).
    """
    vault_path = get_vault_path()
    if not vault_path:
        return {"error": "VAULT_PATH not configured."}

    lint_results = await asyncio.to_thread(lint_vault_sync, vault_path)
    stats_results = await asyncio.to_thread(vault_stats_sync, vault_path)

    from server.maintenance import reconcile_maintenance_queue
    return await asyncio.to_thread(
        reconcile_maintenance_queue,
        vault_path, lint_results, stats_results, auto_confirm,
    )


# ---------------------------------------------------------------------------
# Tool 22: get_maintenance_queue
# ---------------------------------------------------------------------------

async def get_maintenance_queue(
    task_type: str | None = None,
    status: str | None = None,
) -> list[dict]:
    """View maintenance tasks in the queue.

    Args:
        task_type: Filter by type — "merge_candidate", "promote_to_topic",
            "stale_topic_refresh", "orphan_fix", "missing_concept_stub".
        status: Filter by status — "pending", "confirmed", "processing",
            "done", "rejected".  Defaults to non-terminal statuses.
    """
    vault_path = get_vault_path()
    if not vault_path:
        return [{"error": "VAULT_PATH not configured."}]

    from server.maintenance import get_pending_tasks
    return await asyncio.to_thread(
        get_pending_tasks, vault_path, task_type, status,
    )


# ---------------------------------------------------------------------------
# Tool 23: resolve_maintenance_task
# ---------------------------------------------------------------------------

async def resolve_maintenance_task(
    task_id: int,
    action: str = "confirm",
    reason: str = "",
) -> dict:
    """Confirm, reject, or complete a maintenance task.

    Args:
        task_id: The task ID from the maintenance queue.
        action: "confirm", "reject", or "complete".
        reason: Optional reason (used for rejections).
    """
    vault_path = get_vault_path()
    if not vault_path:
        return {"error": "VAULT_PATH not configured."}

    from server.maintenance import confirm_task, reject_task, complete_task

    if action == "confirm":
        return await asyncio.to_thread(confirm_task, vault_path, task_id)
    elif action == "reject":
        return await asyncio.to_thread(reject_task, vault_path, task_id, reason)
    elif action == "complete":
        return await asyncio.to_thread(complete_task, vault_path, task_id)
    else:
        return {"error": f"Invalid action: {action}. Must be confirm, reject, or complete."}


# ---------------------------------------------------------------------------
# Tool 24: export_db_state
# ---------------------------------------------------------------------------

async def export_db_state() -> dict:
    """Export authority-layer database tables to JSON for backup.

    Exports: concept_registry, concept_aliases, concept_merge_history,
    maintenance_queue.  The rebuildable index layer (compile_state,
    compile_deps) is excluded — it can be rebuilt from vault files.
    """
    vault_path = get_vault_path()
    if not vault_path:
        return {"error": "VAULT_PATH not configured."}

    from server.database import export_authority_state
    return await asyncio.to_thread(export_authority_state, vault_path)


# ---------------------------------------------------------------------------
# Tool 25: backfill_registry
# ---------------------------------------------------------------------------

async def backfill_registry() -> dict:
    """Populate the concept registry from existing wiki frontmatter.

    Scans wiki/concepts/, wiki/methods/, and wiki/papers/ to backfill:
    - Concepts and methods into concept_registry
    - Paper → concept references into compile_deps
    - compile_state entries using the current compile schema version

    Does NOT create Compile IR (that requires LLM). It is a lightweight
    registry rebuild helper for the current vault contents.
    """
    vault_path = get_vault_path()
    if not vault_path:
        return {"error": "VAULT_PATH not configured."}

    from server.concept_registry import backfill_registry_from_wiki
    return await asyncio.to_thread(backfill_registry_from_wiki, vault_path)


# ---------------------------------------------------------------------------
# Tool 25: paper-distill-extract
# ---------------------------------------------------------------------------

async def write_compile_ir(citekey: str, ir_json: dict) -> dict:
    """Validate and persist an Extract-stage IR produced by the agent.

    Writes to ``.state/ir/{citekey}.json``.  The agent is responsible for
    the LLM extraction; this tool does schema validation and storage.

    Required top-level fields in ir_json:
    - citekey, title, authors, candidate_concepts, tension_fields
    tension_fields must contain: limitations, assumptions, open_questions,
    negative_results (each a list).

    Args:
        citekey: Paper identifier (e.g. "brohan2023rt2").
        ir_json: The IR dict produced by the agent.
    """
    vault_path = get_vault_path()
    if not vault_path:
        return {"error": "VAULT_PATH not configured."}

    from server.compile_ir import write_ir
    return await asyncio.to_thread(write_ir, vault_path, citekey, ir_json)


# ---------------------------------------------------------------------------
# Tool 26: knowledge-compile-resolve
# ---------------------------------------------------------------------------

async def resolve_compile_ir(citekeys: list[str]) -> list[dict]:
    """Entity-link candidate_concepts in raw IRs against the concept registry.

    For each citekey, reads ``.state/ir/{citekey}.json``, maps each
    candidate concept to its canonical registry entry (registering new ones
    as needed), and writes ``.state/ir/{citekey}_resolved.json``.

    This is the pure-Python Resolve stage — no LLM calls.

    Args:
        citekeys: List of paper citekeys to resolve.
    """
    vault_path = get_vault_path()
    if not vault_path:
        return [{"error": "VAULT_PATH not configured."}]

    from server.compile_ir import resolve_ir
    results = []
    for citekey in citekeys:
        result = await asyncio.to_thread(resolve_ir, vault_path, citekey)
        result["citekey"] = citekey
        results.append(result)
    return results


# ---------------------------------------------------------------------------
# Tool 27: knowledge-compile-publish
# ---------------------------------------------------------------------------

async def commit_compile_result(
    page_id: str,
    page_type: str,
    content: str,
    frontmatter: dict,
    ir_path: str | None = None,
    deps: list[dict] | None = None,
) -> dict:
    """Write compiled markdown + atomically update compile_state/compile_deps.

    This is the EDC Write stage's sole exit point.  Unlike upsert_wiki_article
    (generic safe write), this tool is compile-aware: it records compile
    metadata in SQLite and detects manual-edit conflicts via content_hash.

    Args:
        page_id: Logical ID — citekey for papers, slug for concepts/topics.
        page_type: "paper" | "concept" | "method" | "topic" | "query".
        content: Full markdown body (without frontmatter block).
        frontmatter: Dict of frontmatter fields to render.
        ir_path: Optional path to resolved IR JSON for traceability.
        deps: Optional list of deps: [{dep_type, dep_id, dep_version}].
    """
    vault_path = get_vault_path()
    if not vault_path:
        return {"error": "VAULT_PATH not configured."}

    from server.compile_ir import commit_compile_result as _commit
    return await asyncio.to_thread(
        _commit, vault_path, page_id, page_type, content, frontmatter, ir_path, deps,
    )


# ---------------------------------------------------------------------------
# Tool 28: idea-tension-signals
# ---------------------------------------------------------------------------

async def query_tension_signals(
    min_occurrence: int = 2,
    topic: str | None = None,
) -> dict:
    """Aggregate tension signals from all resolved Compile IRs.

    Scans `.state/ir/*_resolved.json` and returns:
    - recurring_limitations: limitations in ≥ min_occurrence papers
    - all_assumptions: flat list for LLM conflict detection
    - open_question_clusters: open questions grouped by keywords
    - negative_results: flat list of negative/null results

    Use this in the idea-workbench skill to ground research gap analysis
    in structured, IR-sourced evidence rather than heuristic keyword scanning.

    Args:
        min_occurrence: Minimum papers a limitation must appear in (default 2).
        topic: Optional topic filter (must match paper's topics list).
    """
    vault_path = get_vault_path()
    if not vault_path:
        return {"error": "VAULT_PATH not configured."}

    from server.compile_ir import aggregate_tension_signals
    return await asyncio.to_thread(
        aggregate_tension_signals, vault_path, min_occurrence, topic,
    )


# ---------------------------------------------------------------------------
# Tool 29: knowledge-compile-status
# ---------------------------------------------------------------------------

async def get_compile_state(page_id: str, page_type: str = "paper") -> dict:
    """Get the compile state record for a wiki page.

    Returns compile_version, schema_version, compiled_at, ir_path,
    and content_hash for the given page.

    Args:
        page_id: Page identifier (citekey or slug).
        page_type: "paper" | "concept" | "method" | "topic" | "query" (default "paper").
    """
    vault_path = get_vault_path()
    if not vault_path:
        return {"error": "VAULT_PATH not configured."}

    from server.compile_ir import get_compile_state as _get_state
    result = await asyncio.to_thread(_get_state, vault_path, page_id, page_type)
    return result or {"found": False, "page_id": page_id, "page_type": page_type}


# ---------------------------------------------------------------------------
# Tool 31: execute_maintenance_task
# ---------------------------------------------------------------------------

async def execute_maintenance_task(task_id: int) -> dict:
    """Execute a confirmed maintenance task through the Phase 3 controller.

    Supported task types:
    - merge_candidate      → execute_merge
    - promote_to_topic     → execute_promote
    - stale_topic_refresh  → execute_refresh

    Tasks without a controller yet remain pending/confirmed and return an error.
    """
    vault_path = get_vault_path()
    if not vault_path:
        return {"error": "VAULT_PATH not configured."}

    from server.maintenance import _load_task, execute_merge, execute_promote, execute_refresh

    task = await asyncio.to_thread(_load_task, vault_path, task_id)
    if "error" in task:
        return task

    task_type = task.get("task_type")
    if task_type == "merge_candidate":
        return await asyncio.to_thread(execute_merge, vault_path, task_id)
    if task_type == "promote_to_topic":
        return await asyncio.to_thread(execute_promote, vault_path, task_id)
    if task_type == "stale_topic_refresh":
        return await asyncio.to_thread(execute_refresh, vault_path, task_id)
    return {"error": f"No execution controller implemented for task type '{task_type}'"}


# ---------------------------------------------------------------------------
# Tool 32: enqueue_maintenance_task
# ---------------------------------------------------------------------------

async def enqueue_maintenance_task(
    task_type: str,
    payload: dict,
    confidence: float = 1.0,
    status: str = "pending",
    auto_confirm: bool = False,
) -> dict:
    """Create a maintenance task explicitly.

    Use this after a human or agent has adjudicated a candidate and decided
    it should become a real maintenance action. This is the proper path for
    concept merges, promotions, and refreshes that do not originate directly
    from `reconcile_maintenance`.
    """
    vault_path = get_vault_path()
    if not vault_path:
        return {"error": "VAULT_PATH not configured."}

    from server.maintenance import enqueue_task
    return await asyncio.to_thread(
        enqueue_task,
        vault_path,
        task_type,
        payload,
        confidence=confidence,
        status=status,
        auto_confirm=auto_confirm,
    )


# ---------------------------------------------------------------------------
# Tool 32: idea-trigger-candidates
# ---------------------------------------------------------------------------

async def query_trigger_candidates(user_topics: list[str] | None = None) -> dict:
    """Return advanced Phase 3 trigger candidates for maintenance and ideation.

    This is a narrowed view over `analyze_knowledge_graph` focused on:
    - contradiction_candidates
    - recurring_limitation_spikes
    - cross_cluster_bridges
    - benchmark_evaluation_splits
    """
    vault_path = get_vault_path()
    if not vault_path:
        return {"error": "VAULT_PATH not configured."}

    result = await asyncio.to_thread(analyze_knowledge_graph_sync, vault_path, user_topics)
    if "error" in result:
        return result

    gaps = result.get("gaps", {})
    return {
        "paper_count": result.get("paper_count", 0),
        "concept_count": result.get("concept_count", 0),
        "trigger_candidates": {
            "contradiction_candidates": gaps.get("contradiction_candidates", []),
            "recurring_limitation_spikes": gaps.get("recurring_limitation_spikes", []),
            "cross_cluster_bridges": gaps.get("cross_cluster_bridges", []),
            "benchmark_evaluation_splits": gaps.get("benchmark_evaluation_splits", []),
        },
    }




# ---------------------------------------------------------------------------
# Tools: crgp-prepare-context / crgp-save-sections
# ---------------------------------------------------------------------------

async def prepare_crgp_context(citekey: str) -> dict:
    """Return paper source evidence and metadata for LLM-driven CRGP generation.

    Reads the wiki frontmatter, source evidence markdown, and structured
    sidecar (figures, tables, equations) so the LLM has everything needed
    to write grounded CRGP sections.  Also returns any previously stored
    sections from compile_state.managed_blocks_json.

    Args:
        citekey: Paper citekey (e.g. "brohan2023rt2").
    """
    vault_path = get_vault_path()
    if not vault_path:
        return {"error": "VAULT_PATH not configured."}

    from server.crgp_tools import prepare_crgp_context as _prepare
    return await asyncio.to_thread(_prepare, vault_path, citekey)


async def save_crgp_sections(
    citekey: str,
    sections: dict,
    confidence: float = 0.93,
    metadata: dict | None = None,
) -> dict:
    """Persist LLM-generated CRGP sections to the wiki MD and SQLite compile_state.

    Rebuilds the full wiki page body from the provided sections and the
    existing frontmatter metadata, then calls commit_compile_result to
    atomically update both the markdown file and compile_state (version
    bump, managed_blocks_json, content_hash).

    sections must contain all 7 keys:
        Context, Related Work, Gap, Proposal, Key Results, Discussion, Next Steps

    When ``metadata`` is provided (candidate_concepts + tension_fields), the
    function also writes the IR to .state/ir/ and resolves concepts, so that
    aggregate_tension_signals() can include this paper in gap analysis.

    Args:
        citekey:    Paper citekey.
        sections:   Dict mapping section name → markdown prose text.
        confidence: Confidence to record (default 0.93 for LLM-generated).
        metadata:   Optional structured metadata for IR persistence (see
                    crgp_tools.save_crgp_sections for full schema).
    """
    vault_path = get_vault_path()
    if not vault_path:
        return {"error": "VAULT_PATH not configured."}

    from server.crgp_tools import save_crgp_sections as _save
    return await asyncio.to_thread(_save, vault_path, citekey, sections, confidence, metadata)
