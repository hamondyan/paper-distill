# Index Maintenance

The index is not updated automatically after business MCP writes. This file covers when to run `qmd update` vs `qmd embed -f`, and how to diagnose a sick index.

## After a round of writes

The common flow is:

1. Business MCP call (`upsert_wiki_page`, `merge_concept`, etc.) writes or rewrites Markdown.
2. The lexical/collection index is now behind. Run `qmd update`.
3. If the user will immediately query semantic retrieval on the new content, run `qmd embed -f` after `qmd update`.

If the user is not going to search the new content this turn, you can recommend `qmd update` and skip the embed step. Embeddings are the expensive part; do not force them unless needed.

## When `qmd update` is enough

- Routine writes where the user expects to continue the conversation without querying the new page right away.
- Small edits to existing pages (concept merges, lint fixups).
- Multi-page batches — run `qmd update` once at the end of the batch, not per page.

## When `qmd embed -f` is also needed

- The user said "now search for X" immediately after a write.
- The new page contains key terminology not already in similar vault pages (vector index would miss it).
- You just created a new concept page and the user will semantic-query for it this turn.

## Health checks

`qmd status` is the first stop. It reports collection readiness and index freshness. If the user says retrieval "feels stale", run `qmd status` before guessing.

If a collection is missing or misconfigured:

```bash
qmd collection list
qmd collection show canon-papers
qmd collection add <vault>/wiki/papers --name canon-papers
```

If the human-written collection summary is missing or stale:

```bash
qmd context list
qmd context add qmd://canon-papers "Canonical distilled papers"
```

## What not to do

- Do not run `qmd embed -f` on every write. It is expensive and rarely necessary in the same turn.
- Do not run `qmd update` mid-batch when you are still writing; batch the writes first.
- Do not edit indexed collections by hand to "fix" retrieval — the Markdown is the source of truth, rewrite via MCP and then update the index.
