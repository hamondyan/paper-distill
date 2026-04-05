"""
Zotero integration for Paper Distill v2.

Two public async functions:
  - add_papers:    dispatch to local-first export, web API creation, or disabled mode
  - search_papers: full-text search against an existing Zotero library in web_api mode
"""
from __future__ import annotations

import asyncio
import json
import logging
import re
import tempfile
from pathlib import Path

import httpx
from pyzotero import zotero

from server.paper_utils import canonical_item_url, canonical_pdf_url, paper_id

logger = logging.getLogger("paper-distill.zotero")

# ---------------------------------------------------------------------------
# Topic tag -> Zotero collection name
# ---------------------------------------------------------------------------
TOPIC_COLLECTION_MAP: dict[str, str] = {
    "llm-reasoning":          "LLM",
    "rag-retrieval":          "LLM",
    "llm-agents":             "LLM",
    "code-generation":        "LLM",
    "multimodal":             "Multimodal",
    "diffusion-models":       "Generative Models",
    "reinforcement-learning": "RL",
}


# ---------------------------------------------------------------------------
# CrossRef metadata enrichment
# ---------------------------------------------------------------------------
_CROSSREF_HEADERS = {
    "User-Agent": "paper-distill/2.0 (https://github.com/Eclipse-Cj/paper-distill-mcp)",
}


async def _fetch_crossref(doi: str) -> dict:
    """Resolve full metadata for *doi* via the CrossRef API.

    Returns a dict with whichever of {title, authors, journal, year, abstract}
    could be parsed.  Returns ``{}`` on any failure.
    """
    if not doi:
        return {}

    url = f"https://api.crossref.org/works/{doi}"
    try:
        async with httpx.AsyncClient(timeout=15.0, headers=_CROSSREF_HEADERS) as client:
            resp = await client.get(url)
            if resp.status_code != 200:
                logger.debug("CrossRef lookup failed for %s: HTTP %d", doi, resp.status_code)
                return {}
            item = resp.json().get("message", {})
    except Exception as exc:
        logger.debug("CrossRef lookup error for %s: %s", doi, exc)
        return {}

    # -- authors --
    authors: list[str] = []
    for a in item.get("author", []):
        given = a.get("given", "")
        family = a.get("family", "")
        if family:
            authors.append(f"{given} {family}".strip())

    # -- year --
    year: int | None = None
    for field in ("published-print", "published-online", "created"):
        parts = item.get(field, {}).get("date-parts", [[]])
        if parts and parts[0] and parts[0][0]:
            year = parts[0][0]
            break

    # -- journal --
    container = item.get("container-title", [])
    journal = container[0] if container else ""

    # -- abstract (strip JATS XML) --
    abstract = item.get("abstract", "")
    if abstract:
        abstract = re.sub(r"<[^>]+>", "", abstract)

    # -- title --
    titles = item.get("title", [])
    title = titles[0] if titles else ""

    result: dict = {}
    if title:
        result["title"] = title
    if authors:
        result["authors"] = authors
    if journal:
        result["journal"] = journal
    if year:
        result["year"] = year
    if abstract:
        result["abstract"] = abstract

    if result:
        logger.info("CrossRef enriched DOI %s: got %s", doi, ", ".join(result.keys()))
    return result


async def _enrich_paper(paper: dict) -> dict:
    """Fill missing *title*/*authors* from CrossRef when a DOI is present.

    Mutates and returns *paper*.
    """
    doi = paper.get("doi", "")
    if doi and not (paper.get("title") or "").strip():
        enriched = await _fetch_crossref(doi)
        for key, value in enriched.items():
            if not paper.get(key):
                paper[key] = value
    return paper


# ---------------------------------------------------------------------------
# Author parsing
# ---------------------------------------------------------------------------

def _parse_authors(raw) -> list[dict]:
    """Turn author strings / lists into Zotero creator dicts.

    Handles:
      - list:  ["John Smith", "Jane Doe"]
      - str:   "Smith, John; Doe, Jane"  or  "John Smith, Jane Doe"
    """
    creators: list[dict] = []

    if isinstance(raw, list):
        names = raw
    elif isinstance(raw, str):
        names = [n.strip() for n in (raw.split(";") if ";" in raw else raw.split(",")) if n.strip()]
    else:
        return creators

    for name in names:
        if not name:
            continue
        if "," in name:
            parts = name.split(",", 1)
            creators.append({
                "creatorType": "author",
                "lastName": parts[0].strip(),
                "firstName": parts[1].strip() if len(parts) > 1 else "",
            })
        else:
            parts = name.strip().split()
            if len(parts) >= 2:
                creators.append({
                    "creatorType": "author",
                    "lastName": parts[-1],
                    "firstName": " ".join(parts[:-1]),
                })
            else:
                creators.append({"creatorType": "author", "name": name})

    return creators


# ---------------------------------------------------------------------------
# Collection helpers
# ---------------------------------------------------------------------------

def _resolve_collection(
    zot: zotero.Zotero,
    name: str,
    cache: dict[str, str],
) -> str:
    """Return the collection key for *name*, creating the collection if needed."""
    if name in cache:
        return cache[name]

    # Try to create
    resp = zot.create_collections([{"name": name}])
    if isinstance(resp, dict) and "successful" in resp:
        for _, item in resp["successful"].items():
            key = item.get("data", {}).get("key", item.get("key", ""))
            cache[name] = key
            return key

    # Fallback: reload all collections and look again
    for coll in zot.collections():
        d = coll.get("data", {})
        cache[d.get("name", "")] = d.get("key", "")
    return cache.get(name, "")


def _load_collections(zot: zotero.Zotero) -> dict[str, str]:
    """Return ``{name: key}`` for every collection in the library."""
    cache: dict[str, str] = {}
    for coll in zot.collections():
        d = coll.get("data", {})
        cache[d.get("name", "")] = d.get("key", "")
    return cache


def _collection_for_paper(
    paper: dict,
    zot: zotero.Zotero,
    cache: dict[str, str],
) -> str | None:
    """Pick the right collection key for *paper* based on its topic tags."""
    explicit = str(paper.get("collection_name", "")).strip()
    if explicit:
        return _resolve_collection(zot, explicit, cache)

    # Check explicit matched topic first
    matched = paper.get("_matched_topic", "")
    if matched and matched in TOPIC_COLLECTION_MAP:
        return _resolve_collection(zot, TOPIC_COLLECTION_MAP[matched], cache)

    # Fallback: scan topic_tags
    for tag in paper.get("topic_tags", []):
        key = tag.lower().replace(" ", "-")
        if key in TOPIC_COLLECTION_MAP:
            return _resolve_collection(zot, TOPIC_COLLECTION_MAP[key], cache)

    return None


# ---------------------------------------------------------------------------
# Build a Zotero item dict from a paper
# ---------------------------------------------------------------------------

def _paper_to_item(
    paper: dict,
    zot: zotero.Zotero,
    coll_cache: dict[str, str],
) -> dict:
    """Convert *paper* dict into a Zotero ``journalArticle`` template."""
    tpl = zot.item_template("journalArticle")

    tpl["title"] = paper.get("title", "")
    tpl["DOI"] = paper.get("doi", "")
    tpl["url"] = canonical_item_url(paper)
    tpl["publicationTitle"] = (
        paper.get("journal")
        or paper.get("venue")
        or paper.get("venue_raw")
        or paper.get("venue_normalized", "")
    )
    tpl["date"] = (
        paper.get("published_date")
        or paper.get("date")
        or str(paper.get("year", ""))
    )
    tpl["abstractNote"] = paper.get("abstract", "")

    creators = _parse_authors(paper.get("authors", ""))
    if creators:
        tpl["creators"] = creators

    tags = [{"tag": t} for t in paper.get("topic_tags", [])]
    tags.append({"tag": "paper-distill"})
    tpl["tags"] = tags

    extra_parts: list[str] = []
    if paper.get("citekey"):
        extra_parts.append(f"Citation Key: {paper['citekey']}")
    if paper.get("tldr"):
        extra_parts.append(f"TLDR: {paper['tldr']}")
    if paper.get("relevance_note"):
        extra_parts.append(f"Relevance: {paper['relevance_note']}")
    if extra_parts:
        tpl["extra"] = "\n".join(extra_parts)

    coll_key = _collection_for_paper(paper, zot, coll_cache)
    if coll_key:
        tpl["collections"] = [coll_key]

    return tpl


def _zotero_uri_for_key(key: str) -> str:
    return f"zotero://select/library/items/{key}" if key else ""


def _attachment_title(url: str) -> str:
    if "arxiv.org" in url:
        return "Full Text PDF (arXiv)"
    return "Full Text PDF"


def _attachment_path(directory: str, paper: dict, url: str) -> Path:
    pid = paper_id(paper).replace(":", "-").replace("/", "-")
    return Path(directory) / f"{pid}.pdf"


async def _download_attachment_pdf(paper: dict, directory: str) -> tuple[str, str, str] | None:
    url = canonical_pdf_url(paper)
    if not url:
        return None

    try:
        async with httpx.AsyncClient(timeout=60.0, follow_redirects=True) as client:
            resp = await client.get(url)
            resp.raise_for_status()
    except Exception as exc:
        logger.warning("Could not download PDF attachment for %s: %s", paper.get("title", ""), exc)
        return None

    target = _attachment_path(directory, paper, url)
    target.write_bytes(resp.content)
    return (_attachment_title(url), str(target), url)


def _create_linked_pdf_attachment(
    zot: zotero.Zotero,
    parent_key: str,
    title: str,
    url: str,
) -> None:
    tpl = zot.item_template("attachment", linkmode="linked_url")
    tpl["title"] = title
    tpl["url"] = url
    tpl["contentType"] = "application/pdf"
    zot.create_items([tpl], parentid=parent_key)


def _local_export_path(export_dir: str, paper: dict) -> Path:
    stem = str(paper.get("citekey", "")).strip()
    if not stem:
        stem = paper_id(paper).replace(":", "-").replace("/", "-")
    return Path(export_dir).expanduser() / f"{stem}.csl.json"


def _paper_to_csl_item(paper: dict) -> dict:
    venue = (
        paper.get("journal")
        or paper.get("venue")
        or paper.get("venue_raw")
        or paper.get("venue_normalized", "")
    )
    year = paper.get("year")
    authors: list[dict] = []
    for creator in _parse_authors(paper.get("authors", "")):
        if creator.get("lastName"):
            authors.append(
                {
                    "family": creator.get("lastName", ""),
                    "given": creator.get("firstName", ""),
                }
            )
        elif creator.get("name"):
            authors.append({"literal": creator.get("name", "")})

    note_lines = []
    if paper.get("tldr"):
        note_lines.append(f"TLDR: {paper['tldr']}")
    if paper.get("relevance_note"):
        note_lines.append(f"Relevance: {paper['relevance_note']}")
    pdf_url = canonical_pdf_url(paper)
    if pdf_url:
        note_lines.append(f"Preferred PDF: {pdf_url}")

    item = {
        "id": paper_id(paper),
        "type": "article-journal",
        "title": paper.get("title", ""),
        "author": authors,
        "container-title": venue,
        "URL": canonical_item_url(paper),
        "DOI": paper.get("doi", ""),
        "keyword": ", ".join(str(tag) for tag in paper.get("topic_tags", []) if tag),
        "abstract": paper.get("abstract", ""),
        "note": "\n".join(note_lines),
    }
    if year:
        item["issued"] = {"date-parts": [[year]]}
    return {key: value for key, value in item.items() if value not in ("", [], None)}


def _write_local_exports(papers: list[dict], export_dir: str) -> list[dict]:
    export_root = Path(export_dir).expanduser()
    export_root.mkdir(parents=True, exist_ok=True)

    results: list[dict] = []
    for paper in papers:
        target = _local_export_path(str(export_root), paper)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(
            json.dumps([_paper_to_csl_item(paper)], ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        results.append(
            {
                "key": "",
                "zotero_uri": "",
                "zotero_mode": "local_first",
                "zotero_status": "local_exported",
                "zotero_import_path": str(target),
                "attachment_url": canonical_pdf_url(paper),
                "canonical_item_url": canonical_item_url(paper),
            }
        )
    return results


def _disabled_results(papers: list[dict]) -> list[dict]:
    return [
        {
            "key": "",
            "zotero_uri": "",
            "zotero_mode": "disabled",
            "zotero_status": "disabled",
            "zotero_import_path": "",
            "attachment_url": canonical_pdf_url(paper),
            "canonical_item_url": canonical_item_url(paper),
        }
        for paper in papers
    ]


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

async def add_papers(
    papers: list[dict],
    library_id: str = "",
    api_key: str = "",
    *,
    mode: str = "web_api",
    export_dir: str = "",
) -> list[dict]:
    """Add *papers* to a Zotero user library.

    Each paper dict should contain some combination of:
        doi, title, authors, journal, year/date/published_date,
        abstract, topic_tags, citekey, tldr, relevance_note.

    Papers missing a title but carrying a DOI are automatically enriched via
    CrossRef before being pushed.

    Returns a list of successfully created Zotero item dicts.
    On total failure returns ``[]``.
    """
    if not papers:
        return []

    # Enrich concurrently
    await asyncio.gather(*[_enrich_paper(p) for p in papers])

    normalized_mode = str(mode or "web_api").strip().lower().replace("-", "_")
    if normalized_mode == "disabled":
        return _disabled_results(papers)

    if normalized_mode == "local_first":
        if not export_dir:
            return [{"error": "Local-first Zotero mode requires an export_dir"}]
        try:
            return await asyncio.to_thread(_write_local_exports, papers, export_dir)
        except Exception as exc:
            logger.error("local Zotero export failed: %s", exc)
            return [{"error": f"Local Zotero export failed: {exc}"}]

    if not library_id or not api_key:
        return [{"error": "ZOTERO_LIBRARY_ID and ZOTERO_API_KEY required for web_api mode"}]

    with tempfile.TemporaryDirectory(prefix="paper-distill-zotero-") as tmpdir:
        attachments = await asyncio.gather(
            *[_download_attachment_pdf(paper, tmpdir) for paper in papers]
        )

        # pyzotero is synchronous -- run in a thread
        def _sync_create() -> list[dict]:
            zot = zotero.Zotero(library_id, "user", api_key)
            coll_cache = _load_collections(zot)

            items = [_paper_to_item(p, zot, coll_cache) for p in papers]
            if not items:
                return []

            results: list[dict] = []
            batch_size = 50
            for i in range(0, len(items), batch_size):
                batch = items[i : i + batch_size]
                batch_attachments = attachments[i : i + batch_size]
                try:
                    resp = zot.create_items(batch)
                    if isinstance(resp, dict):
                        successful = resp.get("successful", {})
                        for batch_index, item_data in successful.items():
                            try:
                                local_idx = int(batch_index)
                            except (TypeError, ValueError):
                                local_idx = None
                            key = item_data.get("key", "") or item_data.get("data", {}).get("key", "")
                            if key:
                                item_data["key"] = key
                                item_data["zotero_uri"] = _zotero_uri_for_key(key)
                                if local_idx is not None and 0 <= local_idx < len(batch_attachments):
                                    attachment = batch_attachments[local_idx]
                                    if attachment:
                                        try:
                                            zot.attachment_both([(attachment[0], attachment[1])], parentid=key)
                                            item_data["attachment_title"] = attachment[0]
                                            item_data["attachment_url"] = attachment[2]
                                            item_data["attachment_imported"] = True
                                        except Exception as exc:
                                            logger.warning(
                                                "Attachment import failed for %s: %s",
                                                key,
                                                exc,
                                            )
                                            try:
                                                _create_linked_pdf_attachment(
                                                    zot,
                                                    key,
                                                    attachment[0],
                                                    attachment[2],
                                                )
                                                item_data["attachment_title"] = attachment[0]
                                                item_data["attachment_url"] = attachment[2]
                                                item_data["attachment_imported"] = False
                                                item_data["attachment_linked_url"] = True
                                            except Exception as linked_exc:
                                                logger.warning(
                                                    "Linked PDF attachment fallback failed for %s: %s",
                                                    key,
                                                    linked_exc,
                                                )
                            results.append(item_data)
                        failed = resp.get("failed", {})
                        if failed:
                            logger.warning("Failed items in batch: %s", failed)
                    elif isinstance(resp, list):
                        for local_idx, item_data in enumerate(resp):
                            key = item_data.get("key", "") or item_data.get("data", {}).get("key", "")
                            if key:
                                item_data["key"] = key
                                item_data["zotero_uri"] = _zotero_uri_for_key(key)
                                attachment = batch_attachments[local_idx] if local_idx < len(batch_attachments) else None
                                if attachment:
                                    try:
                                        zot.attachment_both([(attachment[0], attachment[1])], parentid=key)
                                        item_data["attachment_title"] = attachment[0]
                                        item_data["attachment_url"] = attachment[2]
                                        item_data["attachment_imported"] = True
                                    except Exception as exc:
                                        logger.warning(
                                            "Attachment import failed for %s: %s",
                                            key,
                                            exc,
                                        )
                                        try:
                                            _create_linked_pdf_attachment(
                                                zot,
                                                key,
                                                attachment[0],
                                                attachment[2],
                                            )
                                            item_data["attachment_title"] = attachment[0]
                                            item_data["attachment_url"] = attachment[2]
                                            item_data["attachment_imported"] = False
                                            item_data["attachment_linked_url"] = True
                                        except Exception as linked_exc:
                                            logger.warning(
                                                "Linked PDF attachment fallback failed for %s: %s",
                                                key,
                                                linked_exc,
                                            )
                        results.extend(resp)
                except Exception as exc:
                    logger.error("Zotero create_items error: %s", exc)
                    # Continue with partial results rather than raising
            return results

        try:
            return await asyncio.get_running_loop().run_in_executor(None, _sync_create)
        except Exception as exc:
            logger.error("add_papers failed: %s", exc)
            return []


async def search_papers(
    query: str,
    library_id: str = "",
    api_key: str = "",
    limit: int = 20,
    *,
    mode: str = "web_api",
) -> list[dict]:
    """Search the Zotero library and return matching items.

    Each returned dict contains: key, title, doi, authors, year, abstract,
    journal, tags, url.

    Returns ``[]`` on failure.
    """
    if not query:
        return []

    normalized_mode = str(mode or "web_api").strip().lower().replace("-", "_")
    if normalized_mode != "web_api":
        return [{"error": f"Zotero search is unavailable in {normalized_mode} mode"}]

    if not library_id or not api_key:
        return [{"error": "ZOTERO_LIBRARY_ID and ZOTERO_API_KEY required for web_api mode"}]

    def _sync_search() -> list[dict]:
        zot = zotero.Zotero(library_id, "user", api_key)
        raw_items = zot.items(q=query, limit=limit, sort="relevance")

        results: list[dict] = []
        for item in raw_items:
            data = item.get("data", {})
            creators = data.get("creators", [])
            author_names: list[str] = []
            for c in creators:
                first = c.get("firstName", "")
                last = c.get("lastName", "")
                name = c.get("name", "")
                if last:
                    author_names.append(f"{first} {last}".strip())
                elif name:
                    author_names.append(name)

            results.append({
                "key": data.get("key", ""),
                "title": data.get("title", ""),
                "doi": data.get("DOI", ""),
                "authors": author_names,
                "year": data.get("date", ""),
                "abstract": data.get("abstractNote", ""),
                "journal": data.get("publicationTitle", ""),
                "tags": [t.get("tag", "") for t in data.get("tags", [])],
                "url": data.get("url", ""),
            })
        return results

    try:
        return await asyncio.get_running_loop().run_in_executor(None, _sync_search)
    except Exception as exc:
        logger.error("search_papers failed: %s", exc)
        return []
