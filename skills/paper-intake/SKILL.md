---
name: paper-intake
description: Use when the user wants to discover papers, summarize a candidate, ingest approved papers, directly add an arXiv URL or arXiv DOI, or process inbox approvals.
---

# Paper Intake

## Overview

Move papers from discovery to raw evidence without bypassing the human approval boundary. The visible path is `inbox/ -> raw/evidence/ -> wiki/papers/`.
For read/index work, consult `docs/qmd-cli.md` and runtime `qmd --help`.

## Available Tools

| Tool | Purpose |
|------|---------|
| `discover_papers` | Search, score, deduplicate, and write inbox stubs |
| `approve_papers` | Mark selected inbox stubs approved from chat or explicit selections |
| `ingest_and_read` | Capture approved inbox notes or one/many agent-resolved arXiv identities |
| `upsert_wiki_page` | Create canonical paper pages after reading and distilling |
| `check_concept_alias` | Resolve uncertain concept names before creating core concept pages |

## Routing Decision

Execute this decision tree before any tool call:

1. User asked to approve recommended inbox candidates: resolve their chat selection to recommended paper IDs or inbox paths, then call `approve_papers(input_value=...)`.
2. User asked to approve every pending inbox candidate: call `approve_papers(input_value="all")`.
3. User asked to ingest approvals: call `ingest_and_read(input_value="approved")`.
4. User provided arXiv URL(s), arXiv ID(s), or arXiv DOI value(s): call `ingest_and_read(input_value=...)` directly. Batch multiple resolved identifiers into one call when possible.
5. User provided title(s), acronym(s), alias(es), project name(s), or mixed natural paper references: the agent must resolve each reference to an arXiv URL first, then call `ingest_and_read` with the resolved arXiv identities. Do not ask for a second confirmation after resolving.
6. User asked for discovery without asking to ingest specific papers: call `discover_papers(query=...)`, then stop and offer to approve selected inbox stubs from chat or explain that the user can add `#approved` in the note body.
7. User asked whether something is already in the vault or wants to read local evidence: use QMD CLI directly, usually `qmd query` or `qmd get`.
8. User wants a canonical paper page after capture and reading: distill the returned raw evidence, then call `upsert_wiki_page(page_type="paper", ...)`.

## Approval Rules

- Approval is file-native. Only a plain `#approved` tag in the inbox note body counts.
- `approve_papers` is the chat-native way to write that same `#approved` body marker for selected inbox notes.
- Frontmatter status fields and filenames do not permit approved-batch ingest.
- Never ingest unapproved inbox notes.
- Do not edit `raw/evidence/` by hand. It is normally read-only after capture; capture repair may rewrite the same paper ID.

## Ingest Rules

- `ingest_and_read(input_value="approved")` reads approved inbox notes and writes captured Markdown to `raw/evidence/`.
- `ingest_and_read(input_value=<identifier_or_batch>)` accepts one or many arXiv URLs, arXiv IDs, or arXiv DOI values.
- Natural references such as `openvla`, exact paper titles, project names, and acronyms are agent-resolved before MCP capture. If the agent cannot find a credible arXiv URL for a reference, report it as unresolved and do not include it in the tool call.
- Do not ask the user to confirm agent-resolved arXiv URLs before calling `ingest_and_read`.
- Report resolved inputs, unresolved inputs, each captured paper's `paper_id`, title, raw evidence path, and any errors.
- If capture succeeds but later processing reports a warning, keep the successful file write and explain the warning.
- If concept compounding fails during ingest, report it clearly; the new paper still enters the vault.

## Canonical Page Creation

After reading and distilling captured evidence:

1. Use `qmd query` to find related papers and concepts.
2. Use `qmd get` for any cited local pages you need to inspect.
3. Create or refresh the paper page with `upsert_wiki_page(page_type="paper", target=..., frontmatter=..., body=...)`.
4. Create concept pages only for core concepts, using `check_concept_alias` first when the canonical surface is uncertain.
5. If a paper-intake conversation surfaces a durable insight about why a paper matters, save the distilled takeaway to `insights/conversations/` through the Python write path. Do not save verbatim transcripts or edit insight files by hand.

## QMD CLI Guidance

- Use QMD CLI directly for `qmd query`, `qmd get`, `qmd status`, `qmd update`, `qmd embed -f`, and collection/context health.
- Check `docs/qmd-cli.md` first for the Paper Distill mapping.
- If command details are uncertain, follow runtime `qmd --help`.

## Skill / Tool Contract

This skill is responsible for intent routing, enforcing approval, summarizing outcomes, and suggesting the next useful action.

Python tools are responsible for deterministic I/O, path safety, capture, and structured errors.
