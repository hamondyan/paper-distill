"""Paper search modules -- thin wrappers over academic APIs.

Search functions return ``list[dict]`` with normalised keys:
    title, year, doi, authors, abstract, source, citation_count,
    open_access_url, code_url, tldr, venue

Utility functions:
    lookup_unpaywall(doi)  -- resolve OA link for a DOI
    resolve_crossref(doi)  -- resolve full metadata for a DOI
    dedup_merge(papers)    -- deduplicate and merge multi-source results
"""

from .arxiv_search import search_arxiv, search_arxiv_query, search_arxiv_title_author
from .semantic_scholar import search_semantic_scholar
from .openalex import search_openalex
from .dblp_search import search_dblp
from .papers_with_code import search_papers_with_code
from .unpaywall import lookup_unpaywall
from .crossref import resolve_crossref
from .merger import dedup_merge

__all__ = [
    "search_arxiv",
    "search_arxiv_query",
    "search_arxiv_title_author",
    "search_semantic_scholar",
    "search_openalex",
    "search_dblp",
    "search_papers_with_code",
    "lookup_unpaywall",
    "resolve_crossref",
    "dedup_merge",
]
