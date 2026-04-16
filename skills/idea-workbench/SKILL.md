---
name: idea-workbench
description: Use when the user asks for research ideas, gap analysis, open problems, novel angles, what to work on, or wants to curate idea notes from local paper evidence.
---

# Idea Workbench

## Overview

Turn local evidence into editable research idea notes. Ideas and distilled conversation notes are knowledge assets, so writes go through Python tools rather than direct hand edits.

## Available Tools

| Tool | Purpose |
|------|---------|
| `status` | Confirm qmd readiness before retrieval |
| `kb_search` | Search canonical, insight, or raw scopes through qmd |
| `kb_get` | Fetch individual evidence pages |
| `upsert_wiki_page` | Write idea and conversation assets |
| `check_concept_alias` | Normalize concept references before writing |

## Generate Ideas

1. Read the user's research direction from the conversation and `settings.json` when available.
2. Use `kb_search(query=..., scope="canon")` to find relevant papers and concepts.
3. Use `kb_get` to inspect the strongest local evidence.
4. Search `scope="insights"` to avoid duplicating existing idea or conversation assets.
5. Draft fewer, stronger ideas grounded in explicit local evidence.

## Write Idea Notes

Create or update `insights/ideas/{slug}.md` with:

```python
upsert_wiki_page(
    page_type="idea",
    target=slug,
    frontmatter={
        "idea_state": "active",
        "topics": topics,
        "related_papers": related_papers,
        "related_concepts": related_concepts,
    },
    body=body,
)
```

Recommended sections:

- `Summary`
- `Local Evidence`
- `Hypothesis / Bridge`
- `Kill Criteria`
- `Next Step`

## Write Conversation Notes

When the useful asset is a distilled conversation takeaway rather than a research idea, write:

```python
upsert_wiki_page(
    page_type="conversation",
    target=slug,
    frontmatter={
        "source_layer": "insights",
        "related_concepts_topk": related_concepts[:3],
    },
    body=body,
)
```

Do not store verbatim transcripts.

## Curate Ideas

- Use `kb_search(scope="insights")` before creating a new idea.
- If an idea is rejected, parked, or superseded, update `idea_state`, `decision_reason`, `decision_at`, and `superseded_by` in the note.
- Keep negative knowledge in the idea note itself.
- Rank ideas by local evidence, novelty, feasibility, and kill criteria clarity.
- Offer targeted follow-ups: search related papers, create a core concept page, or capture a conversation insight.

## Rules

- Ground every idea in local paper or concept evidence.
- State assumptions and conflicts explicitly.
- Prefer specific testable ideas over broad speculation.
- Use Python tools for all `insights/ideas/` and `insights/conversations/` writes.

## Skill / Tool Contract

This skill is responsible for research judgment, evidence selection, concise idea framing, and curation decisions.

Python tools are responsible for deterministic writes, path safety, qmd indexing, and structured errors.
