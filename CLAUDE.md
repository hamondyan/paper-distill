# CLAUDE.md

Agent-specific guidance for Paper Distill. Rules here are load-bearing across commands and skills — consult them before editing the vault or routing a user request.

## Read This First

- Source of truth is Markdown under the configured vault path. Business MCP writes; QMD reads/indexes.
- Skills are medium-grained: pick the one that matches the user's intent, then follow its routing decision tree. Do not freelance across skill boundaries.
- Never edit files in `wiki/papers/`, `wiki/concepts/`, `insights/ideas/`, or `insights/conversations/` directly. Always route through `upsert_wiki_page` so schema validation runs.
- Never edit files in `raw/evidence/` — it is the preserved capture.

## Core Flow

```
/discover -> agent presents chat-only candidates -> /ingest <resolved arXiv URL|ID|DOI> -> raw evidence -> paper-distillation skill or distill_paper writes wiki page -> /lint
```

The agent resolves natural paper names before capture. Do not pass unresolved titles, acronyms, aliases, or project names to the MCP ingest tool.

## Insights Triggers

Canonical paper and concept pages are the bulk of vault content, but insights (`insights/conversations/`, `insights/ideas/`) are where durable taste and cross-paper synthesis live. These layers only fill up when the agent proactively offers them — the user rarely asks by name.

**After each distillation**, scan the session for cross-cutting observations and offer to capture them:

- If two or more distilled papers take opposing approaches to the same problem, or if a method from one paper directly explains a limitation in another, offer to write an `insights/conversations/` note (via `upsert_wiki_page(page_type="conversation", ...)`).
- If the distillation surfaced a research question the user seemed interested in but no paper answers, offer to write an `insights/ideas/` note (via `upsert_wiki_page(page_type="idea", ...)`).

Offer, do not auto-write. Present the candidate in one or two sentences and let the user accept or decline. Do not re-offer the same candidate if the user declined.

**After each batch of distillations** (two or more papers in one session), the idea-workbench skill should proactively propose two or three candidate ideas grounded in the distilled evidence. Keep proposals concrete and evidence-linked; skip this step if the batch is thematically scattered.

## When To Use Which Skill

- `paper-intake` — chat-only discovery and direct capture to `raw/evidence/`.
- `paper-distillation` — `raw/evidence/` → `wiki/papers/` cognitive step.
- `knowledge-workbench` — research questions against the vault, concept maintenance, lint triage.
- `idea-workbench` — generating and curating `insights/ideas/` and `insights/conversations/`.
- `qmd-reference` — QMD CLI syntax, collection handles, post-write refresh.

If the user's request spans two skills, route to the most specific one and call out the handoff in your response.

## Post-Write Rhythm

After any batch of `upsert_wiki_page` / `merge_concept` calls:

1. Tell the user `qmd update` is separate and needed for retrieval to reflect the writes.
2. Only suggest `qmd embed -f` when the user will immediately query semantic retrieval on the new content.

Do not run `qmd update` mid-batch.
