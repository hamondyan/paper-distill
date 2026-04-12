---
name: knowledge-workbench
description: Use when the user asks research questions against the approved vault, wants wiki synthesis saved, requests compile/update wiki, asks for canonical paper page refresh, runs /query, /compile, /lint, or wants wiki health and maintenance work.
---

# Knowledge Workbench

## Overview

Use approved evidence and hidden IR to answer, compile, and maintain the Obsidian wiki. Read machine data through `query-library`; never treat `_index.md` files as backend truth.

## Query

1. Classify the question: factual, comparative, landscape, cross-cutting, or coverage gap.
2. Call `query-library` for relevant sections; prefer `wiki/papers`, concepts, methods, topics, and `sources/evidence`.
3. Read the relevant pages, follow backlinks, and state gaps explicitly instead of inventing coverage.
4. Save substantive answers to `insights/queries/{slug}.md` with frontmatter for question, source pages, referenced papers/concepts/topics, derived actions, and promotion targets.
5. Report what was answered, what asset was created, and what could be compiled or searched next.

## Compile

Use the EDC path for structured compilation:

1. **Extract:** read `sources/evidence` plus source PDF/HTML context; submit required IR through `paper-distill-extract(citekey, ir_json)` so hidden JSON lands in `.state/ir/`.
2. **Resolve:** call `knowledge-compile-resolve(citekeys)` to normalize concepts through the registry.
3. **Write:** call `knowledge-compile-publish(page_id, page_type, content, frontmatter, ir_path, deps)` to refresh managed sections while preserving manual sections such as `## My Notes`.

For lightweight refresh after intake, update canonical `wiki/papers` from evidence + hidden IR, add backlinks, and create concept stubs only when a concept is referenced by at least two papers.

## Maintain

1. Run `wiki-lint`, then `library-stats` for deterministic structure and coverage.
2. Use `reconcile_maintenance(auto_confirm=true|false)` and inspect `get_maintenance_queue(...)`.
3. Execute confirmed merge/promote/refresh tasks with `execute_maintenance_task(task_id)`.
4. For manual work, use `enqueue_maintenance_task(...)` first, then execute only after adjudication.
5. Present a maintainer report: broken links, missing metadata, uncompiled evidence, stale topics, orphaned articles, confirmed tasks, and likely knowledge impact.

## Write Path Rules

Two tools can both write wiki pages but serve different purposes — **never mix them in the same compile flow**:

| Tool | Purpose | Updates `compile_state`? |
|------|---------|--------------------------|
| `knowledge-compile-publish` | EDC Write phase — records `content_hash`, deps, version | **Yes** |
| `upsert_wiki_article` | One-off writes outside EDC (concept stubs, method pages) | **No** |

Rules:
1. Any paper wiki page that goes through Extract → Resolve → Write **must** use `knowledge-compile-publish`
2. Concept/method stubs created outside the EDC flow use `upsert_wiki_article`
3. **Never** call `upsert_wiki_article` on a page previously written by `knowledge-compile-publish` — it silently corrupts `content_hash`
4. When unsure, call `knowledge-compile-status(page_id, page_type)` first

## Manual Section Protection

Before calling `knowledge-compile-publish`:
1. Read the existing file and check for sections marked `## My Notes`, `## Personal Takeaways`, `## Action Items`, or `## Follow-up`
2. If present: append those sections **verbatim** after the generated content block before passing to the tool
3. The tool itself does not merge — merging is the caller's (your) responsibility
4. If the tool returns `manual_edit_conflict: true`, **stop immediately**, report the conflict to the user, and do not overwrite

## Concept Registration Rules

Tool behavior and editorial rules are intentionally separate:
- `knowledge-compile-resolve` auto-registers on first reference (the registry entry is needed for the Resolve phase)
- **The "two-paper rule" is an editorial rule**: only create a `wiki/concepts/{slug}.md` stub page after `list_concepts_tool(min_paper_count=2)` confirms the concept appears in two or more papers
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

**Neither layer does:**
- Tools do not judge whether a paper is "good enough" — that is the human inbox decision
- This Skill does not write files directly — all file writes go through tools
- Tools do not read user intent — they only execute the parameters they receive
