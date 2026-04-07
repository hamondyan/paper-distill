---
name: wiki-lint
description: Use when the user says "/lint", "check wiki health", "wiki维护", "检查知识库", "broken links", "orphaned articles", "wiki audit", "知识库维护", or wants to inspect and repair the wiki for structural issues.
---

# Wiki Lint

Health check and maintenance for the wiki. Deterministic checks run via `lint_vault` MCP tool; only semantic checks need LLM judgment. Present results like a maintainer's inspection of a living knowledge graph.

## Workflow

### Step 1: Run Deterministic Checks

Call `lint_vault` MCP tool. It returns a structured report covering:

1. **Orphaned articles** — wiki files with 0 incoming backlinks
2. **Broken backlinks** — `[[links]]` pointing to nonexistent files
3. **Missing frontmatter** — required YAML fields absent per section schema
4. **Stale indexes** — `_index.md` files missing or outdated
5. **Uncompiled papers** — `raw/notes/` with `compiled: false`
6. **Missing concept stubs** — concepts referenced from papers but no article exists

### Step 2: Semantic Checks (LLM)

These require judgment and cannot be automated:

- **Concept gaps:** Topics with ingested papers but no concept article. Use `query_vault(section="concepts")` and compare against paper topics.
- **Outdated summaries:** Topic landscape articles not updated after recent compilations. Compare `wiki/topics/` updated dates against latest compiled paper dates.
- **Advanced trigger candidates:** inspect `query_trigger_candidates()` for:
  - contradiction candidates
  - recurring limitation spikes
  - cross-cluster bridges
  - benchmark evaluation splits

### Step 3: Present Report

```
Wiki Health Report — {date}

{For each check with count > 0, list items}

Overall health: {from lint_vault result}
```

Also summarize the likely knowledge impact of fixing the current issues:
- which pages would be refreshed
- which missing concepts or topics would become visible
- which confirmed maintenance tasks are ready to execute

### Step 4: Fix

- **Auto-fixable:** Stale indexes (rebuild), missing concept stubs (create stub if referenced by ≥2 papers)
- **Needs /compile:** Uncompiled papers
- **Needs review:** Orphaned articles (ask user: link or remove?)
- **Controller-backed:** Confirmed merge/promote/refresh tasks can be executed via `execute_maintenance_task(task_id)`

Suggested loop:

1. `lint_vault`
2. `vault_stats`
3. `reconcile_maintenance(auto_confirm=true|false)`
4. Review `get_maintenance_queue(...)`
5. Execute selected confirmed tasks with `execute_maintenance_task(task_id)`

For manual/adjudicated maintenance actions that do not come from lint/stats directly:

6. `enqueue_maintenance_task(task_type, payload, ...)`
7. `execute_maintenance_task(task_id)`

Ask user: "Fix auto-fixable issues now?" If yes, proceed.
