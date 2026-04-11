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

## Rules

- `wiki/papers` is the canonical paper workspace; `sources/evidence` is the evidence layer.
- Frontmatter quality drives Obsidian CLI/Bases, backlinks, and future queries.
- Preserve human-authored sections; if managed blocks conflict, report the conflict instead of overwriting.
- Use Obsidian for visible reading and navigation, but keep hidden IR under `.state/`.
