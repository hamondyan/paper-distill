---
name: paper-intake
description: Use when the user wants chat-only paper discovery, candidate summaries, direct arXiv URL/ID/arXiv DOI ingest, or natural paper names resolved before capture.
---

# Paper Intake

## Overview

Move papers from discovery to raw evidence without passing unresolved names to capture. The visible path is chat-only discovery -> `raw/evidence/` -> `wiki/papers/`.
For read/index work, consult `docs/qmd-cli.md` and runtime `qmd --help`.

## Available Tools

| Tool | Purpose |
|------|---------|
| `discover_papers` | Search, score, deduplicate, and return transient candidates for chat presentation |
| `ingest_and_read` | Capture one or many resolved arXiv URLs, IDs, or arXiv DOI values |
| `upsert_wiki_page` | Create canonical paper pages after reading and distilling |
| `check_concept_alias` | Resolve uncertain concept names before creating core concept pages |

## Routing Decision

Execute this decision tree before any tool call:

1. User asked for discovery without asking to ingest specific papers: call `discover_papers(query=...)`, present returned candidates in chat, apply the agent-side presentation guidance in [references/post-discovery-rescoring.md](references/post-discovery-rescoring.md), then stop.
2. User selects a candidate from the current conversation: resolve that candidate to an arXiv URL, arXiv ID, or arXiv DOI value, then call `ingest_and_read(input_value=...)`.
3. User provided arXiv URL(s), arXiv ID(s), or arXiv DOI value(s): call `ingest_and_read(input_value=...)` directly. Batch multiple resolved identifiers into one call when possible.
4. User provided title(s), acronym(s), alias(es), project name(s), or mixed natural paper references: resolve each reference to an arXiv URL, ID, or arXiv DOI value first, then call `ingest_and_read` with only the resolved identities. Do not pass unresolved names to MCP.
5. User asked whether something is already in the vault or wants to read local evidence: use QMD CLI directly, usually `qmd query` or `qmd get`.
6. User wants a canonical paper page after capture and reading: hand off to the `paper-distillation` skill.

## Core Rules

- **Discovery is chat-only.** Treat `discover_papers` results as transient candidates. Present them in chat and stop unless the user also gave a specific resolved identity to capture.
- **Ingest captures only resolved identities.** `ingest_and_read` accepts arXiv URLs, arXiv IDs, and arXiv DOI values. Natural references are agent-resolved before the MCP call. Do not edit `raw/evidence/` by hand. See [references/ingest-rules.md](references/ingest-rules.md) for the resolved/unresolved reporting contract and capture repair behavior.
- **Canonical pages are a separate skill.** Distillation from `raw/evidence/` to `wiki/papers/` is handled by the `paper-distillation` skill. The canonical flow requires 1–5 concepts in `key_concepts_topk`, at least one wikilinked in the body, and `check_concept_alias` before linking uncertain concept surfaces.
- **Conversation insights use the tool path.** If a paper-intake conversation surfaces a durable insight about why a paper matters, save the distilled takeaway to `insights/conversations/` through the Python write path. Do not save verbatim transcripts or edit insight files by hand.

## Post-Discovery Re-scoring

After `discover_papers` returns, the agent should review returned low-score candidates against the user's `research_profile.direction` before presenting results. Promote semantically relevant candidates in the chat summary with a one-line reason. See [references/post-discovery-rescoring.md](references/post-discovery-rescoring.md) for the full playbook.

## QMD CLI Guidance

- Use QMD CLI directly for `qmd query`, `qmd get`, `qmd status`, `qmd update`, `qmd embed -f`, and collection/context health.
- Check `docs/qmd-cli.md` first for the Paper Distill mapping.
- If command details are uncertain, follow runtime `qmd --help`.

## Output Expectations

- After discovery, summarize the strongest candidates, include resolved arXiv identities or arXiv DOI values when available, and stop for user selection.
- After ingest, report exact identifiers processed and unresolved references separately.
- If ingest cannot proceed, explain the blocking state in one sentence before suggesting the next step.

## Skill / Tool Contract

This skill is responsible for intent routing, resolved-identity discipline, summarizing outcomes, and suggesting the next useful action.

Python tools are responsible for deterministic I/O, path safety, capture, and structured errors.
