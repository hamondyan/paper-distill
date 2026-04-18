---
name: paper-distillation
description: Use when the user wants to distill a captured paper into a canonical wiki page, write the wiki page for a paper, or process the raw evidence of a specific paper. Handles the raw/evidence to wiki/papers transition.
---

# Paper Distillation

## Overview

Turn captured raw evidence (`raw/evidence/<paper_id>.md`) into a canonical paper page (`wiki/papers/<slug>.md`). This is the cognitive step where an agent reads a long captured document and produces a short, structured, cross-linked summary with required metadata and concept links.

This skill runs after `paper-intake` has captured the evidence. For read/index work, use `docs/qmd-cli.md` and runtime `qmd --help`.

## Available Tools

| Tool | Purpose |
|------|---------|
| `upsert_wiki_page` | Write the canonical paper page with write-time schema validation |
| `check_concept_alias` | Resolve concept surfaces before linking |

## Routing Decision

1. User asked to distill, write the wiki page for, or process the raw evidence of a specific paper: locate the evidence with `qmd get` or by `paper_id`, read it, extract the structured summary, and call `upsert_wiki_page(page_type="paper", ...)`.
2. User asked to distill a batch: run the single-paper flow per paper sequentially; do not parallelize upserts.
3. User asked to distill but the paper has not been captured yet: hand off to `paper-intake` to run `ingest_and_read` first.

## Required Frontmatter

Every canonical paper page requires:

- `paper_id` — string, e.g. `arxiv:2406.09246`.
- `title` — full paper title.
- `year` — integer publication year.
- `venue` — publication venue or `arXiv` if preprint-only.
- `source_layer` — usually `wiki`.
- `key_concepts_topk` — one to five canonical concept surfaces, each wikilinked at least once in the body.

The write-time validator rejects pages that violate any of these constraints. Do not attempt to work around the validator by hand-editing files.

## Distillation Flow

1. `qmd get` the raw evidence file for the paper.
2. Read the evidence with the extraction questions in [references/extraction-template.md](references/extraction-template.md) in mind.
3. Choose `key_concepts_topk` using the rules in [references/concept-selection.md](references/concept-selection.md) — prefer reusing existing concepts, call `check_concept_alias` when uncertain.
4. Draft the body following the section structure in [references/writing-style.md](references/writing-style.md).
5. Call `upsert_wiki_page(page_type="paper", target=<slug>, frontmatter=..., body=...)`.
6. If any entry in `key_concepts_topk` is new to the vault and meets the bar for a concept page, create it via `upsert_wiki_page(page_type="concept", ...)` in a follow-up call.
7. Recommend `qmd update` after the write round; recommend `qmd embed -f` only if semantic retrieval must reflect the new page immediately.

## Rules

- Distillation is agent-side cognition. Do not copy abstracts verbatim; extract the specific problem, method, results, novelty, and limitations.
- Every `key_concepts_topk` entry must appear as `[[Concept Name]]` at least once in the body.
- Do not edit `raw/evidence/` during distillation — it is the preserved source and must stay intact.
- If the evidence is too shallow to distill (short capture, missing sections), report this as a warning and stop. Do not invent content.
- If the paper draws a strong contrast with an existing vault paper, add a cross-link in the `Relations` section so future `qmd query` runs can surface the comparison.
- After the page lands, apply the Insights Triggers convention in [../../CLAUDE.md](../../CLAUDE.md): offer (do not auto-write) a conversation or idea note if the distillation surfaced a cross-paper observation or an open research question.

## Skill / Tool Contract

This skill is responsible for reading raw evidence, extracting structure, selecting concepts, and producing pages that satisfy write-time validation.

Python tools are responsible for deterministic writes, schema enforcement, and structured errors.
