---
name: knowledge-workbench
description: Use when the user asks research questions against the approved vault, wants wiki synthesis saved, requests compile/update wiki, asks for canonical paper page refresh, runs /query, /compile, /lint, or wants wiki health and maintenance work.
---

# Knowledge Workbench

## Overview

Use approved evidence and hidden IR to answer, compile, and maintain the Obsidian wiki. Read machine data through `query-library`; never treat `_index.md` files as backend truth.

## Available Tools

| Tool | Purpose |
|------|---------|
| `query-library` | Unified read-only query (sections, stats, lint, compile_status, concepts) |
| `compile` | Unified compile pipeline (prepare → save for CRGP; or extract_ir → resolve_ir → publish for EDC) |
| `write-wiki` | One-off wiki writes outside compile (concept stubs, method pages) |
| `concept` | Concept registry: register / resolve / merge |
| `maintain` | Maintenance task lifecycle: reconcile / queue / confirm / reject / execute / enqueue |
| `vault-health` | Combined lint + stats health report |

## Query

1. Classify the question: factual, comparative, landscape, cross-cutting, or coverage gap.
2. Call `query-library(view="sections", section=...)` for relevant sections; prefer `wiki/papers`, concepts, methods, topics, and `sources/evidence`.
3. Read the relevant pages, follow backlinks, and state gaps explicitly instead of inventing coverage.
4. Save substantive answers to `insights/queries/{slug}.md` with frontmatter for question, source pages, referenced papers/concepts/topics, derived actions, and promotion targets.
5. Report what was answered, what asset was created, and what could be compiled or searched next.

## Compile

Use the unified `compile` tool in **two steps**:

1. **Prepare:** call `compile(citekey, step="prepare")` — loads source evidence, paper metadata, and any existing sections.
2. **Generate + Save:** while reading the paper, generate both 7 CRGP sections **and** the structured `metadata` dict; then call `compile(citekey, step="save", sections={...}, metadata={...})`.

The `save` step handles everything atomically: renders the wiki markdown, writes the IR to `.state/ir/`, auto-registers and links concepts, and updates SQLite `compile_state` (including `ir_path`).

**`metadata` schema** (submit alongside `sections` in the same `save` call):

```yaml
candidate_concepts:
  - name: "Vision-Language-Action Models"
    type: method          # concept | method | topic
    aliases: ["VLA"]      # optional
tension_fields:
  limitations:      [str | {claim, source_ref?}]   # required
  assumptions:      [str | {claim, source_ref?}]   # required
  open_questions:   [str | {question, source_ref?}] # required
  negative_results: [str | {claim, source_ref?}]   # required
  failure_modes:    [str | {claim, source_ref?}]   # optional
  transfer_constraints: [str | {claim, source_ref?}] # optional
benchmark_scope: "..."   # optional
claimed_novelty: "..."   # optional
topics: [...]            # optional
```

`metadata` is **always recommended** — omitting it leaves `compile_state.ir_path` null, which silently prevents this paper's limitations and assumptions from appearing in `idea-analyze` gap analysis.

For lightweight prose refresh only (no re-analysis), `step="save"` without `metadata` is acceptable.

> **Internal note**: `extract_ir / resolve_ir / publish` steps remain available for programmatic pipelines but are not part of the standard user workflow.

For lightweight refresh after intake, update canonical `wiki/papers` from evidence + hidden IR, add backlinks, and create concept stubs only when a concept is referenced by at least two papers.

## Maintain

1. Run `vault-health()` for combined structural checks and coverage stats.
2. Use `maintain(action="reconcile", auto_confirm=true|false)` to generate maintenance tasks.
3. View tasks with `maintain(action="queue")`.
4. Execute confirmed tasks with `maintain(action="execute", task_id=...)`.
5. For manual work, use `maintain(action="enqueue", task_type=..., payload=...)` first, then execute only after adjudication.
6. Present a maintainer report: broken links, missing metadata, uncompiled evidence, stale topics, orphaned articles, confirmed tasks, and likely knowledge impact.

## Write Path Rules

Two tools can write wiki pages — **never mix them for the same page**:

| Tool | Purpose | Updates `compile_state`? |
|------|---------|--------------------------|
| `compile(step="save")` | Compile pipeline — records content_hash, deps, version, ir_path | **Yes** |
| `write-wiki` | One-off writes outside compile (concept stubs, method pages) | **No** |

Rules:
1. Any paper wiki page that goes through compile **must** use the `compile` tool
2. Concept/method stubs created outside compile use `write-wiki`
3. **Never** call `write-wiki` on a page previously written by `compile` — it silently corrupts content_hash
4. When unsure, call `query-library(view="compile_status", page_id=...)` first

## Conversation Memory

When a discussion produces a reusable research insight, write a distilled note to `insights/conversations/` through `upsert_wiki_page(page_type="conversation", ...)` or the Python conversation-memory writer. Do not save verbatim transcripts, and do not edit `insights/conversations/` by hand.

## Manual Section Protection

Before calling `compile(step="publish")`:
1. Read the existing file and check for sections marked `## My Notes`, `## Personal Takeaways`, `## Action Items`, or `## Follow-up`
2. If present: append those sections **verbatim** after the generated content block before passing to the tool
3. The tool itself does not merge — merging is the caller's (your) responsibility
4. If the tool returns `manual_edit_conflict: true`, **stop immediately**, report the conflict to the user, and do not overwrite

## Concept Registration Rules

Tool behavior and editorial rules are intentionally separate:
- `compile(step="resolve_ir")` auto-registers on first reference (the registry entry is needed for the Resolve phase)
- **The "two-paper rule" is an editorial rule**: only create a `wiki/concepts/{slug}.md` stub page after `query-library(view="concepts", min_paper_count=2)` confirms the concept appears in two or more papers
- Registry entry exists ≠ wiki page exists

## Rules

- `wiki/papers` is the canonical paper workspace; `sources/evidence` is the evidence layer.
- Frontmatter quality drives Obsidian CLI/Bases, backlinks, and future queries.
- Preserve human-authored sections; if managed blocks conflict, report the conflict instead of overwriting.
- Use Obsidian for visible reading and navigation, but keep hidden IR under `.state/`.

## Skill / Tool Contract

**This Skill is responsible (prompt layer):**
- Parse user intent and route to the correct tool and mode
- Enforce editorial rules (two-paper rule, conflict checks, manual section preservation)
- Merge manual sections into generated content before calling write tools
- Present results in readable form and suggest follow-up actions

**MCP Tool is responsible (Python layer):**
- Perform deterministic I/O (vault read/write, API calls)
- Validate schema and path safety
- Update machine state (compile_state, concept_registry, maintenance_queue)
- Report facts and errors; never make editorial decisions
