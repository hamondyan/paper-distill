---
name: knowledge-workbench
description: Use when the user asks research questions against the vault, wants canonical wiki synthesis saved, asks for concept maintenance, runs QMD CLI read/index flows, or wants business writes and linting.
---

# Knowledge Workbench

## Overview

Use QMD CLI retrieval plus business MCP write tools to answer research questions, maintain canonical pages, and keep the vault healthy. Markdown is the source of truth; read/index work goes through `docs/qmd-cli.md` and runtime `qmd --help`.

## Available Tools

| Tool | Purpose |
|------|---------|
| `upsert_wiki_page` | Write `paper`, `concept`, `idea`, or `conversation` pages |
| `check_concept_alias` | Resolve candidate concept surfaces |
| `merge_concept` | Merge concept aliases and rewrite links |
| `lint_vault` | Report link, alias, footer, and frontmatter issues |

## Query Workflow

1. Run `qmd status` when readiness is uncertain.
2. Classify the question: factual, comparative, landscape, synthesis, or gap-finding.
3. Call `qmd query` first for paper and concept evidence.
4. Use collection filters or path targets when the user explicitly wants `insights` or `raw` layers.
5. Fetch decisive pages with `qmd get`.
6. State evidence gaps plainly instead of inventing coverage.

## Write Workflow

- Use `upsert_wiki_page(page_type="paper", ...)` for canonical paper pages.
- Use `upsert_wiki_page(page_type="concept", ...)` only for core concepts.
- Use `upsert_wiki_page(page_type="idea", ...)` for idea assets.
- Use `upsert_wiki_page(page_type="conversation", ...)` or the Python conversation insight writer for distilled conversation insights.
- Do not edit `wiki/papers/`, `wiki/concepts/`, `insights/ideas/`, or `insights/conversations/` by hand.
- After write-heavy work, tell the user that `qmd update` is separate and `qmd embed -f` is optional when semantic retrieval must reflect the new state immediately.

## Concept Rules

- Only core concepts create `wiki/concepts/` pages.
- Use `check_concept_alias` before creating a concept when the canonical surface is uncertain.
- Call `merge_concept` directly when you are confident two surfaces refer to the same concept.
- After a merge, report rewritten files, alias changes, and separate follow-up guidance for `qmd update` / `qmd embed -f` when needed.

## Conversation Insights

When a discussion produces a reusable research insight, write a distilled note to `insights/conversations/` through `upsert_wiki_page(page_type="conversation", ...)` or the Python conversation insight writer. Do not save verbatim transcripts, and do not edit `insights/conversations/` by hand.

## Health And Index Maintenance

- Use `lint_vault` for dead links, malformed links, alias ambiguity, repeated links, template-like footer linking, and oversized frontmatter.
- Use QMD CLI directly for `qmd status`, `qmd update`, `qmd embed -f`, `qmd collection ...`, and `qmd context ...`.
- Check `docs/qmd-cli.md` first for the Paper Distill mapping.
- If command details are uncertain, follow runtime `qmd --help`.

## Skill / Tool Contract

This skill is responsible for intent routing, evidence-grounded synthesis, concept judgment, and clear reporting.

Python tools are responsible for deterministic I/O, path safety, link rewrites, and structured errors.
