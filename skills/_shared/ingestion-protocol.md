# Shared Ingestion Protocol

The canonical resolve → capture → zotero → write flow for adding papers to the vault.

## Steps

### 1. Resolve Metadata

1. Read `settings.json → paper_distill.research_profile`
2. Prefer exact identifiers: DOI → arXiv ID → canonical paper URL
3. Call `resolve_metadata` for DOI; `fetch_arxiv_record` for arXiv ID
4. Build canonical paper object with: paper_id, title, authors, year, doi, arxiv_id, venue, canonical_pdf_url, canonical_html_url, canonical_item_url

### 2. Deduplicate

1. Call `query-library(section="sources", detail="full")` and `query-library(section="papers", detail="full")`
2. Match by paper_id, DOI, or arXiv ID
3. If exists: report existing paths, do NOT create duplicates

### 3. Capture Source

1. If `arxiv_id` exists: use `capture_arxiv_source` (ar5iv HTML cleaning)
2. If ar5iv fails: automatic PDF fallback via `fetch_pdf_text`
3. Generate `sources/evidence/{date}/{citekey}.md` and `sources/evidence/{date}/{citekey}.assets.json`
4. Treat `sources/evidence/*.md` as the agent-facing inline evidence layer:
   - figures, tables, and display equations should appear near their正文位置
   - `Appendix Snapshot` may remain for summary-only appendix capture
   - `Captured Assets Index` points readers back to the `.assets.json` sidecar
5. Treat `.assets.json` as the authoritative structured evidence layer for sections, figures, tables, equations, and capture provenance

### 4. Generate CRGP-DNL Note

Use `build_crgp_dnl` to create `sources/notes/{date}/{citekey}.md` from cleaned source.

### 5. Zotero Handoff

1. Call `zotero_add`
2. If Zotero fails: keep source layers, report warning clearly — do NOT roll back

### 6. Report

Show: title, source evidence path, source note path, Zotero status, capture fidelity, optional next step (`knowledge-compile`).
