---
name: paper-ingest
description: Use when the user explicitly says "ingest", provides a DOI, arXiv ID, or paper URL, and wants to approve that paper directly into raw/ and Zotero without going through inbox discovery. For more natural user phrasing like "add this paper to my knowledge vault", prefer `paper-add`.
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

## Feedback Loop

- If the user rejects a discovered paper, update `learned_preferences.rejected_keywords`
- If the user explicitly approves, update `accepted_keywords` and `preferred_venues`

## Important

- Direct ingest is a manual approval shortcut — discovery normally goes through `paper-discover`
- Raw/source format must be consistent: prefer `capture_arxiv_source` over raw PDF text
- For user-facing direct-add intent, `paper-add` is the clearer preferred skill
