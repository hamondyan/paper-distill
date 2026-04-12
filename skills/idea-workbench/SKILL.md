---
name: idea-workbench
description: Use when the user asks for research ideas, gap analysis, open problems, novel angles, what to work on, /ideas, 给我一些研究思路, 研究方向, or wants to curate idea notes from local paper evidence.
---

# Idea Workbench

## Overview

Turn local evidence into editable research idea notes. Ideas are first-class Markdown assets under `insights/ideas/`, not transient chat or sidecar artifacts.

## Tool Selection

Three tools serve different analysis granularities — use them in order, they are not interchangeable:

| Tool | Returns | When to use |
|------|---------|-------------|
| `idea-discover` | Broad graph analysis: methodology mismatches, combination opportunities, recurring problems | **Must be called first in every ideation session** |
| `idea-tension-signals` | Structured tension data from resolved IR: recurring limitations, open questions, contradictions | Call after `idea-discover` identifies a promising area |
| `idea-trigger-candidates` | Narrow view: contradiction candidates, limitation spikes, cross-cluster bridges, evaluation benchmark splits | For maintaining triggers and specific hypothesis generation — **not a replacement for `idea-discover`** |

Standard sequence: `idea-discover` → `idea-tension-signals(min_occurrence=2)` → `idea-trigger-candidates` (optional) → read 2-3 reference papers → draft

`idea-trigger-candidates` is a subset view of `idea-discover` output, not an alternative.

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

## Skill / Tool Contract

**This Skill is responsible (prompt layer):**
- Parse user intent and route to the correct tool and mode
- Enforce editorial rules (two-paper rule, similar-idea check before creating new notes)
- Sequence tool calls correctly (`idea-discover` before `idea-tension-signals`)
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
