# v3.0 Architecture

Markdown files are the only source of truth.
`qmd` owns formal search.
Python tools own deterministic writes, validation, and index scheduling.

## Storage Layers

- `inbox/` holds discovery candidates for human approval.
- `raw/evidence/` holds captured source evidence.
- `wiki/papers/` holds agent-owned canonical paper pages.
- `wiki/concepts/` holds agent-owned canonical concept pages.
- `insights/ideas/` holds idea assets written through Python tools.
- `insights/conversations/` holds distilled conversation insights written through Python tools.
- `exports/presentations/` is the direct-write delivery exception.

## Read Surface

- `kb_search(query, scope)` performs qmd-backed semantic search. Supported first-release scopes are `canon`, `insights`, and `raw`.
- `kb_get(id_or_path)` fetches the current file truth for one asset.
- `check_concept_alias(name)` performs deterministic concept alias lookup from concept pages.

## Write Surface

- `upsert_wiki_page(page_type, target, frontmatter, body)` performs entire-page replacement for formal knowledge assets.
- `merge_concept(old, new)` rewrites concept links, updates aliases, and triggers qmd maintenance.
- `kb_update_index` refreshes qmd metadata.
- `kb_reembed_force` rebuilds embeddings.

## First-Release Flow

```text
discover -> approve with #approved -> ingest -> search/get -> lint -> status
```

No filesystem search fallback is allowed for knowledge retrieval. If qmd is missing or unready, the system reports `not_ready`.
