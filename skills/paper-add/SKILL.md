---
name: paper-add
description: Use when the user provides a DOI, arXiv ID, or paper URL and wants to add that already-approved paper directly into the knowledge vault, says "add this paper to knowledge vault", "add this paper to my vault", "把这篇论文直接加入知识库", "直接入库", or /add-paper.
---

# Paper Add

User-confirmed direct-add path: skip `inbox/` and add one explicit paper straight into the approved knowledge base.

## Workflow

### Step 1: Resolve the Paper

1. Read `settings.json → paper_distill.research_profile`
2. Prefer exact identifiers in this order:
   - DOI
   - arXiv ID
   - canonical paper URL
3. Resolve metadata:
   - DOI → call `resolve_metadata`
   - arXiv ID or arXiv URL → construct canonical arXiv metadata and links
   - Other paper/PDF URL → call `fetch_pdf_text` if needed, then infer metadata as far as possible
4. Build one canonical paper object with:
   - `paper_id`
   - `title`
   - `authors`
   - `year`
   - `doi`
   - `arxiv_id`
   - `venue`
   - `canonical_pdf_url`
   - `canonical_html_url`
   - `canonical_item_url`

### Step 2: Check for Existing Copies

1. Call `query_vault(section="raw")` and `query_vault(section="papers")`
2. Match by `paper_id`, DOI, or arXiv ID
3. If the paper already exists:
   - do not create duplicates
   - show the existing raw/wiki paths
   - offer next actions such as `/compile` only if needed

### Step 3: Capture Approved Raw Layers

This paper is already human-approved, so do **not** write to `inbox/`.

1. If `arxiv_id` exists, use the same arXiv capture pipeline as `process-inbox`
   - create `raw/source/{date}/{citekey}.md`
   - clean via ar5iv when available
2. Generate `raw/notes/{date}/{citekey}.md` using the same `CRGP-DNL` structure as normal ingestion
3. Mark the raw note as directly approved by the user

### Step 4: Hand Off to Zotero

1. Call `zotero_add`
2. If Zotero fails: keep the raw layers already written and report the handoff problem clearly — do not roll back the capture

### Step 5: Report and Suggest Next Step

Show:
- title
- raw/source path
- raw/notes path
- Zotero status or import-pack path
- whether the paper was already present
- optional next step: compile into wiki

## Rules

- This is the preferred user-facing path for explicitly user-approved papers
- Skip `inbox/` entirely
- Deduplicate before writing
- Prefer exact identifiers over fuzzy title matching
- Prefer arXiv capture over raw PDF extraction when `arxiv_id` is available
- If metadata is incomplete, be explicit about missing fields
- After successful add, suggest `paper-distill:wiki-compile`

## Relationship to Other Skills

- Use `paper-add` when the user intent is "put this confirmed paper into my knowledge vault now"
- Use `paper-ingest` when the user explicitly says `ingest` or runs `/ingest`
- Use `paper-summarize` when the user wants to inspect a paper before deciding whether to add it
