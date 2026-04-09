---
name: source-ingest
description: Use when the user wants approved inbox notes or a directly supplied DOI/arXiv/URL persisted into `sources/evidence` + `sources/notes`, says "process approved papers", "ingest this paper", "把已批准候选入库", "直接入库", `/process-inbox`, `/add-paper`, or `/ingest`.
---

# Source Ingest

Persist approved evidence into the `sources/` truth layer: capture cleaned source content, generate CRGP-DNL notes, then hand off to Zotero.

## Workflow

1. Determine the ingest mode:
   - approved inbox queue → use `mode="approved_inbox"`
   - explicit DOI/arXiv/URL already approved by the user → use `mode="direct_identifier"`
2. If using the inbox queue, call `query-library(section="inbox", status="approved")` first.
   - If there are no approved candidates, report that and stop.
3. Call `source-ingest(...)`
   - `source-ingest(mode="approved_inbox", status="approved", limit=...)`
   - `source-ingest(mode="direct_identifier", identifier=..., topic_keys=..., collection_name=...)`
4. Summarize: papers exported, source evidence and source note paths, any failures or Zotero warnings
5. If the user wants, trigger `knowledge-compile`

## Parallelization

If >5 approved inbox papers, dispatch subagents (each processing 2-3 papers) to reduce latency. Keep direct-identifier ingest single-threaded so the result is explicit and easy to audit.

## Rules

- Never move `proposed`, `rejected`, or `deferred` notes into `sources/`
- Capture must succeed before Zotero handoff
- If capture or Zotero fails, leave note in inbox with failure metadata
- Skip duplicates already in `sources/notes` or `wiki/`
- User-confirmed direct identifiers should go straight to `mode="direct_identifier"` unless the user explicitly asks to stage inbox review first
