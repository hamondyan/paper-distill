---
name: idea-workbench
description: Use when the user asks for research ideas, gap analysis, open problems, novel angles, what to work on, /ideas, 给我一些研究思路, 研究方向, or wants to curate idea notes from local paper evidence.
---

# Idea Workbench

## Overview

Turn local evidence into editable research idea notes. Ideas are first-class Markdown assets under `insights/ideas/`, not transient chat or sidecar artifacts.

## Generate

1. Read `settings.json -> paper_distill.research_profile` for direction and preferences.
2. Call `idea-discover` for graph and IR gaps.
3. Call `idea-tension-signals(min_occurrence=2)` when contradictions, assumptions, or transfer barriers matter.
4. Call `idea-trigger-candidates()` when looking for recurring limitation spikes, cross-cluster bridges, contradiction candidates, or benchmark/evaluation splits.
5. Read 2-3 referenced papers or concepts for each promising gap before drafting.

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
