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
- `exports/presentations/` is the direct-written delivery area.
- `.state/` holds operational state such as the seen-paper cache.
- `vault-log.md` records vault actions.

## Read Surface

- `kb_search(query, scope)` performs qmd-backed search. Supported scopes are `canon`, `insights`, and `raw`.
- `kb_get(id_or_path)` fetches the current Markdown truth for one asset.
- `check_concept_alias(name)` checks concept names and aliases from `wiki/concepts/`.
- Knowledge retrieval uses `kb_search` and `kb_get`. If qmd binary is missing or unavailable, the read path reports `not_ready`; if required collections are missing or mounted to another vault, it reports `degraded`.

## Write Surface

- `discover_papers(query=None)` writes inbox stubs and updates `.state/seen_papers.json`.
- `ingest_and_read(input_value)` captures approved inbox notes or one direct arXiv URL or arXiv DOI into `raw/evidence/`.
- `upsert_wiki_page(page_type, target, frontmatter, body)` writes `paper`, `concept`, `idea`, or `conversation` pages through Python validation.
- `merge_concept(old, new)` rewrites concept links, adds the old surface as an alias on the target concept, and refreshes qmd.
- `kb_update_index()` refreshes qmd metadata.
- `kb_reembed_force()` rebuilds qmd embeddings.
- `lint_vault()` reports dead links, malformed links, alias ambiguity, repeated links, template-like footer linking, and oversized frontmatter.

## First-Release Flow

```text
discover -> approve with #approved -> ingest -> search/get -> canonical write -> lint -> status
```

Approval is file-native. Only a plain `#approved` tag in the inbox note body allows approved-batch ingest.

## Failure Semantics

- Missing `VAULT_PATH` returns an explicit configuration error.
- Missing or unavailable qmd returns `not_ready` for retrieval.
- The missing qmd collections state returns `degraded` until `status` reconciles the expected collection mounts.
- Raw evidence capture may rewrite an existing `raw/evidence/` file for the same paper ID as capture repair.
- If concept compounding fails during ingest, the paper still enters the vault and the failure is reported.
- Index failure after a successful Python file write is returned as a warning, not as write failure.
