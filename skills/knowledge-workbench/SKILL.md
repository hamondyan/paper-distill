---
name: knowledge-workbench
description: Use when the user asks research questions against the vault, wants canonical wiki synthesis saved, asks for concept maintenance, runs search/get/lint/status flows, or wants qmd index maintenance.
---

# Knowledge Workbench

## Overview

Use qmd-backed retrieval and Python write tools to answer research questions, maintain canonical pages, and keep the vault healthy. Markdown is the source of truth; `kb_search` and `kb_get` are the read path.

## Available Tools

| Tool | Purpose |
|------|---------|
| `status` | Check vault layout and qmd readiness |
| `kb_search` | Search `canon`, `insights`, or `raw` scopes through qmd |
| `kb_get` | Fetch one Markdown asset by ID or path through qmd |
| `upsert_wiki_page` | Write `paper`, `concept`, `idea`, or `conversation` pages |
| `check_concept_alias` | Resolve candidate concept surfaces |
| `merge_concept` | Merge concept aliases and rewrite links |
| `lint_vault` | Report link, alias, footer, and frontmatter issues |
| `kb_update_index` | Refresh qmd metadata |
| `kb_reembed_force` | Rebuild qmd embeddings |

## Query Workflow

1. Run `status` when readiness is uncertain. If qmd is `not_ready`, report that retrieval is unavailable.
2. Classify the question: factual, comparative, landscape, synthesis, or gap-finding.
3. Call `kb_search(query=..., scope="canon")` first for paper and concept evidence.
4. Use `scope="insights"` for idea or conversation assets only when the user asks for those layers.
5. Use `scope="raw"` when the user asks to inspect captured evidence.
6. Fetch decisive pages with `kb_get`.
7. State evidence gaps plainly instead of inventing coverage.

## Write Workflow

- Use `upsert_wiki_page(page_type="paper", ...)` for canonical paper pages.
- Use `upsert_wiki_page(page_type="concept", ...)` only for core concepts.
- Use `upsert_wiki_page(page_type="idea", ...)` for idea assets.
- Use `upsert_wiki_page(page_type="conversation", ...)` or the Python conversation-memory writer for distilled conversation insights.
- If qmd indexing fails after a successful file write, report the warning as an index warning, not as write failure.
- Do not edit `wiki/papers/`, `wiki/concepts/`, `insights/ideas/`, or `insights/conversations/` by hand.

## Concept Rules

- Only core concepts create `wiki/concepts/` pages.
- Use `check_concept_alias` before creating a concept when the canonical surface is uncertain.
- Call `merge_concept` directly when you are confident two surfaces refer to the same concept.
- After a merge, report rewritten files, alias changes, and any qmd warnings.

## Conversation Insights

When a discussion produces a reusable research insight, write a distilled note to `insights/conversations/` through `upsert_wiki_page(page_type="conversation", ...)` or the Python conversation-memory writer. Do not save verbatim transcripts, and do not edit `insights/conversations/` by hand.

## Health And Index Maintenance

- Use `lint_vault` for dead links, malformed links, alias ambiguity, repeated links, template-like footer linking, and oversized frontmatter.
- Use `kb_update_index` after external file changes.
- Use `kb_reembed_force` when embeddings must be rebuilt.
- Use `status` to confirm whether qmd is `ready`, `degraded`, or `not_ready`.

## Skill / Tool Contract

This skill is responsible for intent routing, evidence-grounded synthesis, concept judgment, and clear reporting.

Python tools are responsible for deterministic I/O, path safety, qmd operations, link rewrites, and structured errors.
