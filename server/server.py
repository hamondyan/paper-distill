"""Thin Paper Distill MCP entrypoint."""
from __future__ import annotations

from fastmcp import FastMCP

from server import server_runtime as _rt
from server.idea_tools import register_idea_tools
from server.knowledge_tools import register_knowledge_tools
from server.library_tools import register_library_tools
from server.source_tools import register_source_tools

mcp = FastMCP("paper-distill")

get_vault_path = _rt.get_vault_path
get_topics = _rt.get_topics
get_paper_distill_settings = _rt.get_paper_distill_settings
build_crgp_dnl = _rt.build_crgp_dnl
bind_paper_to_arxiv = _rt.bind_paper_to_arxiv
capture_arxiv_source = _rt.capture_arxiv_source
_zotero_add = _rt._zotero_add
_zotero_runtime = _rt._zotero_runtime
_capture_settings = _rt._capture_settings
_score_rejected_keywords = _rt._score_rejected_keywords
_source_doc_sidecar_payload = _rt._source_doc_sidecar_payload
_load_candidate_sections = _rt._load_candidate_sections
_existing_paper_ids = _rt._existing_paper_ids
_prepare_ingestion_candidate = _rt._prepare_ingestion_candidate
_prepare_direct_add_candidate = _rt._prepare_direct_add_candidate
_resolve_explicit_paper = _rt._resolve_explicit_paper

_SYNC_BINDINGS = (
    "get_vault_path",
    "get_topics",
    "get_paper_distill_settings",
    "search_papers",
    "build_crgp_dnl",
    "bind_paper_to_arxiv",
    "capture_arxiv_source",
    "_zotero_add",
    "_zotero_runtime",
    "_capture_settings",
    "_prepare_ingestion_candidate",
    "_prepare_direct_add_candidate",
    "_resolve_explicit_paper",
    "_existing_paper_ids",
)
_DELEGATED_ASYNC_NAMES = (
    "search_papers",
    "score_papers",
    "query_vault",
    "discover_papers",
    "source_ingest",
    "process_inbox",
    "add_paper",
    "analyze_knowledge_graph",
    "update_learned_preferences",
    "upsert_wiki_article",
    "write_compile_ir",
    "resolve_compile_ir",
    "commit_compile_result",
    "query_tension_signals",
    "get_compile_state",
    "_enrich_inbox_candidate",
    "_prepare_ingestion_candidate",
    "_prepare_direct_add_candidate",
    "_resolve_explicit_paper",
)
_ORIGINAL_BINDINGS = {name: getattr(_rt, name) for name in set(_SYNC_BINDINGS).union(_DELEGATED_ASYNC_NAMES)}
_DELEGATED_WRAPPERS: dict[str, object] = {}


def _delegate_async(name: str):
    async def _wrapped(*args, **kwargs):
        for binding in set(_SYNC_BINDINGS).union(_DELEGATED_ASYNC_NAMES):
            current = globals()[binding]
            wrapper = _DELEGATED_WRAPPERS.get(binding)
            setattr(
                _rt,
                binding,
                _ORIGINAL_BINDINGS[binding] if wrapper is not None and current is wrapper else current,
            )
        return await getattr(_rt, name)(*args, **kwargs)

    _wrapped.__name__ = name
    _wrapped.__doc__ = getattr(_rt, name).__doc__
    _DELEGATED_WRAPPERS[name] = _wrapped
    return _wrapped


def _delegate_sync(name: str):
    def _wrapped(*args, **kwargs):
        for binding in set(_SYNC_BINDINGS).union(_DELEGATED_ASYNC_NAMES):
            current = globals()[binding]
            wrapper = _DELEGATED_WRAPPERS.get(binding)
            setattr(
                _rt,
                binding,
                _ORIGINAL_BINDINGS[binding] if wrapper is not None and current is wrapper else current,
            )
        return getattr(_rt, name)(*args, **kwargs)

    _wrapped.__name__ = name
    _wrapped.__doc__ = getattr(_rt, name).__doc__
    return _wrapped


for _name in _DELEGATED_ASYNC_NAMES:
    globals()[_name] = _delegate_async(_name)

_capture_options = _delegate_sync("_capture_options")
_selected_topics = _delegate_sync("_selected_topics")

register_library_tools(mcp)
register_source_tools(mcp)
register_knowledge_tools(mcp)
register_idea_tools(mcp)


def main():
    mcp.run()


if __name__ == "__main__":
    main()
