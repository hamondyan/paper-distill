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

- Use `upsert_wiki_page(page_type="paper", ...)` for canonical paper pages. Generated paper pages must include required metadata and one to five `key_concepts_topk` entries, with at least one of those concepts linked in the body.
- Use `upsert_wiki_page(page_type="concept", ...)` only for core concepts. Generated concept pages must include `concept`, `aliases`, `source_layer`, and at least one supporting `related_papers_topk` entry.
- Use `upsert_wiki_page(page_type="idea", ...)` for idea assets.
- Use `upsert_wiki_page(page_type="conversation", ...)` or the Python conversation insight writer for distilled conversation insights.
- Do not edit `wiki/papers/`, `wiki/concepts/`, `insights/ideas/`, or `insights/conversations/` by hand.
- After write-heavy work, tell the user that `qmd update` is separate and `qmd embed -f` is optional when semantic retrieval must reflect the new state immediately.

See [references/concept-rules.md](references/concept-rules.md) for concept selection, naming, and merge decisions.

## Conversation Insights

When a discussion produces a reusable research insight, write a distilled note to `insights/conversations/` through `upsert_wiki_page(page_type="conversation", ...)` or the Python conversation insight writer. Do not save verbatim transcripts, and do not edit `insights/conversations/` by hand.

See [references/conversation-insights.md](references/conversation-insights.md) for note structure, trigger heuristics, and examples.

## Concept Maintenance

- Only core concepts create `wiki/concepts/` pages.
- Reuse existing concepts before creating new concept pages.
- Use `check_concept_alias` before creating a concept when the canonical surface is uncertain.
- Call `merge_concept` directly when you are confident two surfaces refer to the same concept.
- After a merge, report rewritten files, alias changes, and separate follow-up guidance for `qmd update` / `qmd embed -f` when needed.

## Health And Index Maintenance

- Use `lint_vault` for dead links, malformed links, alias ambiguity, repeated links, template-like footer linking, oversized frontmatter, paper pages missing concept links, paper key concepts not linked in the body, overly dense paper concept links, and concept pages without supporting papers.
- Use QMD CLI directly for `qmd status`, `qmd update`, `qmd embed -f`, `qmd collection ...`, and `qmd context ...`.
- For a vault health snapshot (counts + lint issues + recent activity), run the `/status` command.
- Check `docs/qmd-cli.md` first for the Paper Distill mapping.
- If command details are uncertain, follow runtime `qmd --help`.

See [references/health-maintenance.md](references/health-maintenance.md) for lint-triage recipes, when to run `qmd embed -f`, and how to interpret specific issue codes.

## Skill / Tool Contract

This skill is responsible for intent routing, evidence-grounded synthesis, concept judgment, and clear reporting.

Python tools are responsible for deterministic I/O, path safety, link rewrites, and structured errors.
