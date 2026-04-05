---
name: wiki-lint
description: Use when the user says "/lint", "check wiki health", "wiki维护", "检查知识库", "broken links", "orphaned articles", "wiki audit", "知识库维护", or wants to inspect and repair the wiki for structural issues.
---

# Wiki Lint

Health check and maintenance for the wiki. Deterministic checks run via `lint_vault` MCP tool; only semantic checks need LLM judgment.

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

### Step 3: Present Report

```
Wiki Health Report — {date}

{For each check with count > 0, list items}

Overall health: {from lint_vault result}
```

### Step 4: Fix

- **Auto-fixable:** Stale indexes (rebuild), missing concept stubs (create stub if referenced by ≥2 papers)
- **Needs /compile:** Uncompiled papers
- **Needs review:** Orphaned articles (ask user: link or remove?)

Ask user: "Fix auto-fixable issues now?" If yes, proceed.
