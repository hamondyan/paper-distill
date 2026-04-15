---
name: idea-workbench
description: Use when the user asks for research ideas, gap analysis, open problems, novel angles, what to work on, /ideas, or wants to curate idea notes from local paper evidence.
---

# Idea Workbench

## Overview

Turn local evidence into editable research idea notes. Ideas are first-class Markdown assets under `insights/ideas/`, not transient chat or sidecar artifacts.

## Available Tools

| Tool | Purpose |
|------|---------|
| `idea-analyze` | One-shot analysis: returns gaps, tension signals, and trigger candidates |
| `query-library` | Read vault sections for follow-up paper reads |

## Generate

1. Read `settings.json -> paper_distill.research_profile` for direction and preferences.
2. Call `idea-analyze(user_topics=..., min_occurrence=2)` — returns a combined analysis with:
   - **gaps**: methodology mismatches, combination opportunities, recurring problems, scaling questions
   - **tension_signals**: recurring limitations, assumptions, open question clusters, negative results
   - **trigger_candidates**: contradiction candidates, limitation spikes, cross-cluster bridges, benchmark evaluation splits
3. Read 2-3 referenced papers or concepts for each promising gap before drafting.

## Write Idea Notes

Create or update `insights/ideas/{idea-id}.md` with frontmatter:

```yaml
type: idea-note
idea_state: active
date: YYYY-MM-DD
topics: []
related_papers: []
related_concepts: []
decision_reason: ""
decision_at: ""
superseded_by: ""
status: saved
```

Use these sections:

- `Summary`
- `Local Evidence`
- `Hypothesis / Bridge`
- `Kill Criteria`
- `Next Step`

## Curate

- Before creating a new note, run the cheap similar-idea check through the existing idea workflow and update related rejected, parked, or active notes when appropriate.
- If an idea is rejected or parked, update `idea_state`, `decision_reason`, `decision_at`, `superseded_by`, and the note body; keep the decision in the note itself instead of creating sidecar records.
- Rank ideas by local evidence, novelty, feasibility, and kill criteria clarity.
- Offer targeted follow-ups: search related papers, promote a topic/concept tension, or queue a maintenance task after explicit adjudication.

## Rules

- Ground every idea in local paper/concept evidence.
- State assumptions and conflicts explicitly.
- Prefer fewer stronger ideas over broad speculative lists.
- Keep negative knowledge in the idea note itself.

## Skill / Tool Contract

**This Skill is responsible (prompt layer):**
- Parse user intent and route to the correct tool
- Enforce editorial rules (similar-idea check before creating new notes)
- Present results in readable form and suggest follow-up actions

**MCP Tool is responsible (Python layer):**
- Perform deterministic I/O (vault read/write, IR graph traversal)
- Validate schema and path safety
- Return structured tension data, graph clusters, and trigger candidates
- Report facts and errors; never make editorial decisions

**Neither layer does:**
- Tools do not decide which ideas are worth pursuing — that is the researcher's judgment
- This Skill does not write idea note files directly — all file writes go through tools
- Tools do not read user intent — they only execute the parameters they receive
