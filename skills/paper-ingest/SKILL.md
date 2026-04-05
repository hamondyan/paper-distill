---
name: paper-ingest
description: Use when the user explicitly says "/ingest", "ingest this paper", or provides a DOI/arXiv ID/URL with clear intent to bypass the discovery queue and write directly to raw/. This is the explicit command path — for conversational phrasing like "add this paper" or "直接入库", use `paper-add` instead.
---

# Paper Ingest

Manual approval shortcut: resolve one paper, capture its source, and create raw notes directly.

## Workflow

### Step 1: Resolve Metadata

1. Read `settings.json → paper_distill.research_profile`
2. Call `resolve_metadata` when a DOI is available
3. Build paper object with DOI, arXiv ID, title, authors, year, venue, and links

### Step 2: Capture Source

If the paper has an arXiv ID, use the same `capture_arxiv_source` pipeline as `process-inbox` to create `raw/source/{date}/{citekey}.md`. This ensures consistent ar5iv HTML-cleaned format across all raw/source files.

If no arXiv ID, call `fetch_pdf_text` (which still tries ar5iv first for arXiv URLs).

### Step 3: Generate CRGP-DNL Note

Use `build_crgp_dnl` to create `raw/notes/{date}/{citekey}.md` from the captured source.

### Step 4: Add to Zotero

Call `zotero_add`. If Zotero fails, keep the raw notes but warn the user.

### Step 5: Report

Show: title, raw/source path, raw/notes path, Zotero status, optional next step (/compile).

## Important

- Direct ingest bypasses the discovery queue — discovery normally goes through `paper-discover`
- Raw/source format must be consistent: prefer `capture_arxiv_source` over raw PDF text
