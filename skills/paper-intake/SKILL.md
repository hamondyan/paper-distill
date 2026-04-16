---
name: paper-intake
description: Use when the user wants to discover papers, summarize a candidate, ingest approved papers, directly add an arXiv URL or DOI, or process inbox approvals.
---

# Paper Intake

## Overview

Move papers from discovery to raw evidence without bypassing the human approval boundary. The visible path is `inbox/ -> raw/evidence/ -> wiki/papers/`.

## Available Tools

| Tool | Purpose |
|------|---------|
| `discover_papers` | Search, score, deduplicate, and write inbox stubs |
| `ingest_and_read` | Capture approved inbox notes or one direct arXiv URL / DOI |
| `kb_search` | Search existing knowledge through qmd |
| `kb_get` | Fetch one existing knowledge asset through qmd |
| `upsert_wiki_page` | Create canonical paper pages after reading and distilling |
| `status` | Check vault and qmd readiness |

## Routing Decision

Execute this decision tree before any tool call:

1. User provided an arXiv URL or arXiv DOI: call `ingest_and_read(input_value=...)`.
2. User asked to ingest approvals: call `ingest_and_read(input_value="approved")`.
3. User asked for discovery: call `discover_papers(query=...)`, then stop and tell the user to approve inbox stubs by adding `#approved` in the note body.
4. User asked whether something is already in the vault: use `kb_search` or `kb_get`.
5. User wants a canonical paper page after capture and reading: distill the returned raw evidence, then call `upsert_wiki_page(page_type="paper", ...)`.

## Approval Rules

- Approval is file-native. Only a plain `#approved` tag in the inbox note body counts.
- Frontmatter status fields, filenames, and conversational approval do not permit approved-batch ingest.
- Never ingest unapproved inbox notes.
- Do not edit `raw/evidence/` by hand. It is normally read-only after capture; capture repair may rewrite the same paper ID.

## Ingest Rules

- `ingest_and_read(input_value="approved")` reads approved inbox notes and writes captured Markdown to `raw/evidence/`.
- `ingest_and_read(input_value=<identifier>)` accepts direct arXiv URLs and arXiv DOI values.
- Report each captured paper's `paper_id`, title, raw evidence path, and any errors.
- If capture succeeds but later processing reports a warning, keep the successful file write and explain the warning.
- If concept compounding fails during ingest, report it clearly; the new paper still enters the vault.

## Canonical Page Creation

After reading and distilling captured evidence:

1. Use `kb_search` to find related papers and concepts.
2. Use `kb_get` for any cited local pages you need to inspect.
3. Create or refresh the paper page with `upsert_wiki_page(page_type="paper", target=..., frontmatter=..., body=...)`.
4. Create concept pages only for core concepts, using `check_concept_alias` first when the canonical surface is uncertain.
5. If a paper-intake conversation surfaces a durable insight about why a paper matters, save the distilled takeaway to `insights/conversations/` through the Python write path. Do not save verbatim transcripts or edit insight files by hand.

## Skill / Tool Contract

This skill is responsible for intent routing, enforcing approval, summarizing outcomes, and suggesting the next useful action.

Python tools are responsible for deterministic I/O, path safety, capture, qmd indexing, and structured errors.
