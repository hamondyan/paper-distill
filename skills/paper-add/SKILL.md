---
name: paper-add
description: Use when the user provides a DOI, arXiv ID, or paper URL and wants to add that already-approved paper directly into the knowledge vault, says "add this paper to knowledge vault", "add this paper to my vault", "把这篇论文直接加入知识库", "直接入库", or /add-paper.
---

# Paper Add

User-confirmed direct-add path: skip `inbox/` and add one explicit paper straight into the approved knowledge base.

## Workflow

Follow the **[Shared Ingestion Protocol](../_shared/ingestion-protocol.md)** for Steps 1-6 (resolve → deduplicate → capture → CRGP-DNL → Zotero → report).

### Add-Specific Behavior

- **Skip inbox**: This path is for user-confirmed papers — write directly to `raw/`, never to `inbox/`
- **Topic matching**: Run `_matched_topics_for_explicit_paper` to auto-tag with configured topics
- **Collection override**: Allow user to specify a custom Zotero collection name
- **Post-add suggestion**: After successful add, suggest `paper-distill:wiki-compile`

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
