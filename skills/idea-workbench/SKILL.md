---
name: idea-workbench
description: Use when the user asks for research ideas, gap analysis, open problems, novel angles, what to work on, or wants to curate idea notes from local paper evidence.
---

# Idea Workbench

## Overview

Turn local evidence into editable research idea notes. Ideas and distilled conversation notes are knowledge assets, so writes go through Python tools rather than direct hand edits. For read/index work, consult `docs/qmd-cli.md` and runtime `qmd --help`.

## Available Tools

| Tool | Purpose |
|------|---------|
| `upsert_wiki_page` | Write idea and conversation assets |
| `check_concept_alias` | Normalize concept references before writing |

## Generate Ideas

1. Read the user's research direction from the conversation and `settings.json` when available.
2. Use `qmd query` to find relevant papers and concepts.
3. Use `qmd get` to inspect the strongest local evidence.
4. Use QMD collections or paths to avoid duplicating existing idea or conversation assets.
5. Draft fewer, stronger ideas grounded in explicit local evidence.

## Write Idea Notes

Use `upsert_wiki_page(page_type="idea", target=<slug>, frontmatter=..., body=...)` to create or update an idea note in `insights/ideas/`. See [references/idea-note-template.md](references/idea-note-template.md) for the full frontmatter shape and the recommended body sections (Summary / Local Evidence / Hypothesis / Kill Criteria / Next Step).

## Write Conversation Notes

Use `upsert_wiki_page(page_type="conversation", target=<slug>, frontmatter=..., body=...)` when the useful asset is a distilled conversation takeaway rather than a research idea. Do not store verbatim transcripts. See [references/conversation-note-template.md](references/conversation-note-template.md) for the frontmatter and body shape.

## Curate Ideas

- Use `qmd query` before creating a new idea.
- If an idea is rejected, parked, or superseded, update `idea_state`, `decision_reason`, `decision_at`, and `superseded_by` in the note rather than deleting it.
- Keep negative knowledge in the idea note itself.
- Rank active ideas by local evidence, novelty, feasibility, and kill-criterion clarity.
- Offer targeted follow-ups: search related papers, create a core concept page, or capture a conversation insight.

See [references/curation-rules.md](references/curation-rules.md) for state transitions, ranking heuristics, and when to retire an idea permanently.

## Rules

- Ground every idea in local paper or concept evidence.
- State assumptions and conflicts explicitly.
- Prefer specific testable ideas over broad speculation.
- Use Python tools for all `insights/ideas/` and `insights/conversations/` writes.
- Use QMD CLI directly for `qmd query`, `qmd get`, `qmd status`, `qmd update`, `qmd embed -f`, and collection/context health.
- Check `docs/qmd-cli.md` first for the Paper Distill mapping.
- If command details are uncertain, follow runtime `qmd --help`.

## When Not To Write Yet

- If the evidence is thin, keep the output as candidate ideas in chat instead of writing a note.
- If the same idea already exists, update or supersede it rather than creating a near-duplicate file.
- If the user only wants exploration, do the retrieval and ranking work first, then ask whether any candidate should be saved.

## Skill / Tool Contract

This skill is responsible for research judgment, evidence selection, concise idea framing, and curation decisions.

Python tools are responsible for deterministic writes, path safety, and structured errors.
