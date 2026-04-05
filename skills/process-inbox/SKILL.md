---
name: process-inbox
description: Use when the user has approved inbox notes and wants them captured into raw/source + raw/notes and handed off to Zotero, says "/process-inbox", "process approved papers", or "把已批准候选入库".
---

# Process Inbox

Move `status=approved` inbox notes through the full ingestion pipeline: capture cleaned arXiv source content, generate CRGP-DNL notes, then hand off to Zotero.

## Workflow

1. Call `query_vault(section="inbox", status="approved")` — if no approved papers, report that and stop
2. Call `process_inbox(...)` for each approved paper
   - On capture failure: leave the note in inbox with a `capture_error` field noting the reason; continue with remaining papers
   - On Zotero failure: mark the note as failed in inbox, warn the user, and continue with remaining papers
3. Summarize: papers exported, raw/source and raw/notes paths, any failures
4. If the user wants, trigger `wiki-compile`

## Parallelization

If >5 approved papers, dispatch subagents (each processing 2-3 papers) to reduce latency. The `process_inbox` MCP tool handles individual papers; coordinate at the skill level.

## Rules

- Never move `proposed`, `rejected`, or `deferred` notes into raw
- Capture must succeed before Zotero handoff
- If capture or Zotero fails, leave note in inbox with failure metadata
- Skip duplicates already in raw/notes or wiki/
