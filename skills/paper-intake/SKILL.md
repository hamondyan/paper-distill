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
6. User asked for discovery without asking to ingest specific papers: call `discover_papers(query=...)`, then stop and offer to approve selected inbox stubs from chat. The file-native approval marker remains an internal implementation detail. After discovery, apply the post-discovery re-scoring pass defined in [references/post-discovery-rescoring.md](references/post-discovery-rescoring.md).
7. User asked whether something is already in the vault or wants to read local evidence: use QMD CLI directly, usually `qmd query` or `qmd get`.
8. User wants a canonical paper page after capture and reading: hand off to the `paper-distillation` skill.

## Core Rules

- **Approval is file-native.** Only a plain `#approved` tag in the inbox note body counts. `approve_papers` is the chat-native way to write that same marker. Never ingest unapproved inbox notes. See [references/approval-rules.md](references/approval-rules.md) for edge cases (frontmatter status fields, code fences, nested notes).
- **Ingest captures only.** `ingest_and_read(input_value="approved")` processes approved inbox notes; batch-ingest accepts arXiv URLs, arXiv IDs, arXiv DOI values. Natural references are agent-resolved before the MCP call. Do not edit `raw/evidence/` by hand. See [references/ingest-rules.md](references/ingest-rules.md) for the resolved/unresolved reporting contract and capture repair behavior.
- **Canonical pages are a separate skill.** Distillation from `raw/evidence/` to `wiki/papers/` is handled by the `paper-distillation` skill. The canonical flow requires 1–5 concepts in `key_concepts_topk`, at least one wikilinked in the body, and `check_concept_alias` before linking uncertain concept surfaces.
- **Conversation insights use the tool path.** If a paper-intake conversation surfaces a durable insight about why a paper matters, save the distilled takeaway to `insights/conversations/` through the Python write path. Do not save verbatim transcripts or edit insight files by hand.

## Post-Discovery Re-scoring

After `discover_papers` returns, the agent should re-read candidates whose heuristic score is 0 and whose `topic_fit` is 0 against the user's `research_profile.direction`. Relevant candidates get a one-line `rescore_reason` appended to the inbox note body so later recommendation rounds can surface them. See [references/post-discovery-rescoring.md](references/post-discovery-rescoring.md) for the full playbook.

## QMD CLI Guidance

- Use QMD CLI directly for `qmd query`, `qmd get`, `qmd status`, `qmd update`, `qmd embed -f`, and collection/context health.
- Check `docs/qmd-cli.md` first for the Paper Distill mapping.
- If command details are uncertain, follow runtime `qmd --help`.

## Output Expectations

- After discovery, summarize the strongest candidates and the reason they are worth approval.
- After approval or ingest, report exact identifiers processed and unresolved references separately.
- If approval or ingest cannot proceed, explain the blocking state in one sentence before suggesting the next step.

## Skill / Tool Contract

This skill is responsible for intent routing, enforcing approval, summarizing outcomes, and suggesting the next useful action.

Python tools are responsible for deterministic I/O, path safety, capture, and structured errors.
