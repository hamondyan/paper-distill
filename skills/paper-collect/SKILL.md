---
name: paper-collect
description: Use when the user says "add to Zotero", "save to Zotero", "收藏这篇论文", "同步到Zotero", "collect papers", or wants papers that are already in raw/ or wiki/ saved to their Zotero library.
---

# Paper Collect

Save already-ingested papers to Zotero. This is for Zotero management, not the ingestion pipeline (use `process-inbox` for that).

## Workflow

### Step 1: Identify Papers

- **By number:** "collect 1, 3" → resolve from today's daily-log
- **By citekey:** "collect black2024-pi0"
- **By title:** fuzzy match against approved raw notes
- **All today:** "collect all"

### Step 2: Resolve Metadata

Read the raw/ note for DOI. If incomplete, call `resolve_metadata` MCP tool.

### Step 3: Add to Zotero

Call `zotero_add` MCP tool. It handles CrossRef enrichment, collection mapping, and deduplication.

### Step 4: Add Zotero Backlink

If the paper has a wiki note, add Zotero link to its header:
```markdown
[[raw/{date}/{citekey}|Raw Note]] | [Zotero](zotero://select/library/items/{zotero_key})
```

### Step 5: Report

```
Collected {N} papers to Zotero:
1. {Title} ({Year}) → Collection: {collection_name}
...
```

If any collected papers have `compiled: false`, suggest: "Run `/compile` to create wiki articles for these papers."

## Important

- Do NOT trigger deep compilation synchronously. Mark as `compiled: false` and suggest batch `/compile` later.
- If Zotero is not configured, report the configuration needed.
- Skip papers already in Zotero (note the duplicate).
