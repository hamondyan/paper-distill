---
name: qmd-reference
description: Use when the user or another skill needs QMD CLI syntax, collection handles, retrieval recipes, or post-write index refresh guidance. Centralizes the read/index surface that sits alongside the Paper Distill business MCP.
---

# QMD Reference

## Overview

QMD CLI is the primary read/index path for this vault. Business MCP tools write Markdown; QMD queries, fetches, and keeps indexes in sync. This skill gives you a fast command index and points at deeper recipes under [references/](references) when a specific scenario needs more detail.

The authoritative source for syntax is `qmd --help` at runtime, with [docs/qmd-cli.md](../../docs/qmd-cli.md) providing the Paper Distill mapping.

## Command Index

| Command | Use it when |
|---------|-------------|
| `qmd query <text>` | Default retrieval. Hybrid search with auto expansion and reranking. |
| `qmd get <path>[:line] [-l N]` | You already know the file or want a specific slice. |
| `qmd status` | Check index and collection health before assuming reads are current. |
| `qmd update` | Catch the index up to Markdown after a round of business writes. |
| `qmd embed -f` | Force-refresh embeddings when semantic retrieval must reflect new writes immediately. |
| `qmd collection list|show|add` | Inspect or repair the five collection mounts. |
| `qmd context list|add` | Inspect or repair human-written collection summaries. |
| `qmd ls [collection[/subpath]]` | List indexed files by collection or path prefix. |

Repo collection handles:

- `canon-papers` → `wiki/papers`
- `canon-concepts` → `wiki/concepts`
- `insights-conversations` → `insights/conversations`
- `insights-ideas` → `insights/ideas`
- `raw-evidence` → `raw/evidence`

## High-Frequency Scenarios

- **Research question, unsure layer**: run `qmd query "<topic>"` without `-c`; then narrow with `-c canon-papers` or `-c canon-concepts` once you see where the evidence lives.
- **Read a specific page**: `qmd get wiki/papers/<slug>.md`; add `:line -l N` for a slice.
- **Just wrote a page, retrieval comes back stale**: run `qmd update`. If the user needs semantic (vector) results to reflect the new page right now, follow with `qmd embed -f`.
- **Index looks broken / collection missing**: `qmd status`, then `qmd collection list` / `qmd collection show <name>`.

See [references/query-recipes.md](references/query-recipes.md) for lexical vs semantic vs filtered search, [references/maintenance.md](references/maintenance.md) for post-write refresh decisions, and [references/common-pitfalls.md](references/common-pitfalls.md) for the mistakes that waste the most time.

## Quick Decision Rules

- Start with `qmd query` when the user asks a question and you do not already know the file.
- Switch to `qmd get` when the search results point at one decisive page you need to quote or inspect closely.
- Run `qmd status` before debugging retrieval health, collection drift, or "why can't qmd see this page?" questions.
- Run `qmd update` after a batch of business writes; reserve `qmd embed -f` for moments when semantic retrieval has to be current immediately.
- Reach for collection or context commands only when the problem is about repo wiring or search scope, not ordinary retrieval.

## Escalation Notes

- If runtime syntax and this skill disagree, trust `qmd --help`.
- If the index looks healthy but results are still poor, go back to the calling skill and tighten the query, collection filter, or page target before assuming QMD is broken.
- If a business-write workflow is incomplete, finish that workflow first; QMD cannot read content that has not been written yet.

## Skill / Tool Contract

This skill is a reference surface for agents that are already holding another task. It does not invoke MCP tools on its own. When another skill (paper-intake, paper-distillation, knowledge-workbench, idea-workbench) needs QMD syntax, route here instead of duplicating command details in each SKILL.md.

For command details not covered here, prefer runtime `qmd --help` over memory.
