---
name: paper-ingest
description: Use when the user explicitly says "/ingest", "ingest this paper", or provides a DOI/arXiv ID/URL with clear intent to bypass the discovery queue and write directly to raw/. This is the explicit command path — for conversational phrasing like "add this paper" or "直接入库", use `paper-add` instead.
---

# Paper Ingest

Manual approval shortcut: resolve one paper, capture its source, and create raw notes directly.

## Workflow

Follow the **[Shared Ingestion Protocol](../_shared/ingestion-protocol.md)** for Steps 1-6 (resolve → deduplicate → capture → CRGP-DNL → Zotero → report).

### Ingest-Specific Behavior

- **Explicit command path**: Triggered by `/ingest` — for conversational phrasing use `paper-add` instead
- **Direct to raw**: Bypasses discovery queue entirely
- **Consistent capture format**: Always prefer `capture_arxiv_source` over raw PDF text

## Important

- Direct ingest bypasses the discovery queue — discovery normally goes through `paper-discover`
- Raw/source format must be consistent: prefer `capture_arxiv_source` over raw PDF text
