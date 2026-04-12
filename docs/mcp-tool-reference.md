# MCP Tool Reference

Complete parameter documentation for all 32 MCP tools.

---

## Library Tools

### search_papers

Search academic papers across CS/AI sources. Returns deduplicated, merged results enriched with stable paper IDs and normalized venue metadata. No ranking or filtering applied — the calling agent handles curation.

**MCP name:** `search_papers`

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `query` | string | yes | — | Free-text search query |
| `sources` | list[string] | no | `null` (all configured) | Override active sources: `arxiv`, `semantic_scholar`, `openalex`, `dblp`, `papers_with_code` |
| `max_results` | int | no | `20` | Maximum results to return |

**Returns:** `list[dict]` — each item has `paper_id`, `title`, `authors`, `year`, `venue`, `abstract`, `doi`, `arxiv_id`, `url`, `citation_count`.

---

### resolve_metadata

Resolve full metadata for a DOI via CrossRef + Unpaywall OA lookup.

**MCP name:** `resolve_metadata`

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `doi` | string | yes | — | DOI string (with or without `doi:` prefix) |

**Returns:** `dict` — merged metadata including `title`, `authors`, `year`, `venue`, `abstract`, `open_access_url`, `canonical_pdf_url`, `license`.

---

### zotero_add

Add papers to Zotero library with auto-metadata enrichment. Dispatches through the configured Zotero mode.

**MCP name:** `zotero_add`

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `papers` | list[dict] | yes | — | Papers to add. Each item must have at least a `paper_id` or `doi`. |

**Returns:** `list[dict]` — each item reports `paper_id`, `status` (`added`, `duplicate`, `error`), and `zotero_key` if added.

---

### zotero_search

Search existing papers in the Zotero library.

**MCP name:** `zotero_search`

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `query` | string | yes | — | Search query |
| `limit` | int | no | `20` | Maximum results |

**Returns:** `list[dict]` — matching Zotero items.

---

### fetch_pdf_text

Fetch and extract text from an open-access paper. For arXiv papers, tries ar5iv HTML first (faster, cleaner), then falls back to PDF. For other URLs, fetches PDF directly.

**MCP name:** `fetch_pdf_text`

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `url` | string | yes | — | Open-access URL (arXiv abstract page, PDF URL, or DOI URL) |
| `max_pages` | int | no | `10` | Maximum pages to extract from PDF |

**Returns:** `string` — extracted plain text.

---

### score_papers

Score a list of papers using the v2 topic-aware deterministic formula. All scoring parameters default to values from `settings.json` if not provided.

**MCP name:** `score_papers`

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `papers` | list[dict] | yes | — | Papers to score |
| `topic_keywords` | list[string] | no | `null` | Override topic keywords |
| `known_dois` | list[string] | no | `null` | DOIs already in library (for novelty) |
| `topics` | dict | no | `null` | Full topics dict override |
| `known_ids` | list[string] | no | `null` | Paper IDs already in library |
| `whitelist_authors` | list[string] | no | `null` | Preferred authors |
| `preferred_venues` | list[string] | no | `null` | Preferred venue names |
| `venue_aliases` | dict | no | `null` | Venue name aliases |
| `venue_tiers` | dict | no | `null` | Tier-S / Tier-A venue lists |
| `runtime_context` | dict | no | `null` | Additional context (e.g., `feedback_count`) |

**Returns:** `list[dict]` — papers with `score_total`, `score_breakdown`, `best_topic`, `matched_topics` added.

---

### query-library

Query the Paper Distill library metadata by parsing YAML frontmatter. Use this instead of reading `_index.md` files.

**MCP name:** `query-library`

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `section` | string | no | `"all"` | `inbox`, `source_evidence`, `papers`, `concepts`, `methods`, `topics`, `queries`, `ideas`, `all` |
| `topic` | string | no | `null` | Filter by topic key |
| `uncompiled_only` | bool | no | `false` | Return only papers without a compile record |
| `status` | string | no | `null` | Filter by frontmatter `status` field |
| `detail` | string | no | `"compact"` | `"compact"` or `"full"` |
| `limit` | int | no | `null` | Maximum items per section |
| `sort_by` | string | no | `"updated_at"` | Sort field |
| `days_back` | int | no | `null` | Filter to items modified within N days |

**Returns:** `dict` — `{ sections: { [section]: [...] }, provider: "obsidian_cli"|"filesystem_scan", total_count }`.

---

### bootstrap-library

Initialize the Paper Distill directory structure inside an Obsidian vault.

**MCP name:** `bootstrap-library`

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `vault_path` | string | no | `null` | Override vault path (defaults to `settings.json` value) |

**Returns:** `dict` — `{ created_dirs: [...], existing_dirs: [...] }`.

---

### update_learned_preferences

Safely update learned preferences in `settings.json`. Atomically appends new items to existing lists without overwriting.

**MCP name:** `update_learned_preferences`

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `accepted_keywords` | list[string] | no | `null` | Keywords to add to accepted list |
| `rejected_keywords` | list[string] | no | `null` | Keywords to add to rejected list |
| `preferred_venues` | list[string] | no | `null` | Venues to add to preferred list |

**Returns:** `dict` — updated preference lists and `feedback_count`.

---

## Source Tools

### source-discover

Search, score, arXiv-bind, and optionally save candidate papers into inbox notes.

**MCP name:** `source-discover`

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `query` | string | no | `null` | Ad-hoc search query (creates a synthetic `ad-hoc` topic) |
| `topic_keys` | list[string] | no | `null` | Topics to run discovery for (defaults to all configured topics) |
| `max_results_per_source` | int | no | `null` | Override per-source result limit |
| `save_to_inbox` | bool | no | `true` | Write inbox cards for top candidates |

**Returns:** `dict` — `{ candidates: [...], saved: int, skipped_duplicates: int, drift_warnings: [...] }`.

---

### source-ingest

Persist approved evidence into the `sources/` truth layer.

**MCP name:** `source-ingest`

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `mode` | string | no | `"approved_inbox"` | `"approved_inbox"` or `"direct_identifier"` |
| `identifier` | string | no | `""` | DOI, arXiv ID, or URL (required for `direct_identifier` mode) |
| `status` | string | no | `"approved"` | Inbox status filter for `approved_inbox` mode |
| `limit` | int | no | `20` | Maximum papers to ingest per call |
| `collection_name` | string | no | `""` | Zotero collection override |
| `topic_keys` | list[string] | no | `null` | Topic keys to assign to directly added papers |

**Returns:** `dict` — `{ processed: int, succeeded: int, failed: int, results: [...] }`.

**Note:** In `approved_inbox` mode, call `query-library(section="inbox", status="approved")` first to confirm approved items exist. The tool itself does not validate `status`.

---

## Knowledge Tools

### wiki-lint

Run deterministic structural health checks on the vault.

**MCP name:** `wiki-lint`

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| *(none)* | | | | |

**Returns:** `dict` — `{ orphaned_articles, broken_backlinks, missing_frontmatter, stale_indexes, uncompiled_papers, missing_concept_stubs, total_issues }` with file lists.

---

### library-stats

Compute vault statistics.

**MCP name:** `library-stats`

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| *(none)* | | | | |

**Returns:** `dict` — paper counts per stage, compilation rate, wiki article counts, per-topic breakdowns, last activity timestamp.

---

### upsert_wiki_article

Create or update a wiki article with path safety guards. For one-off writes outside the EDC pipeline. **Does not update `compile_state`.**

**MCP name:** `upsert_wiki_article`

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `citekey` | string | yes | — | Paper citekey or article slug |
| `section` | string | yes | — | Target wiki section: `papers`, `concepts`, `methods`, `topics` |
| `content` | string | yes | — | Full Markdown content to write |
| `frontmatter` | dict | no | `null` | YAML frontmatter fields to merge |

**Returns:** `dict` — `{ path, created: bool, updated: bool }`.

**Warning:** Do not use on pages previously written by `knowledge-compile-publish` — it will silently break the `content_hash`.

---

### register_concept_tool

Register a concept in the canonical registry.

**MCP name:** `register_concept_tool`

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `canonical` | string | yes | — | Canonical concept name |
| `concept_type` | string | no | `"concept"` | `"concept"`, `"method"`, or `"topic"` |
| `aliases` | list[string] | no | `null` | Additional surface forms for this concept |

**Returns:** `dict` — `{ concept_id, slug, canonical, concept_type, created: bool, merged_into: str|null }`.

---

### resolve_concept_tool

Resolve a surface form to its canonical concept in the registry.

**MCP name:** `resolve_concept_tool`

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `surface_form` | string | yes | — | Surface form to look up |

**Returns:** `dict` — `{ found: bool, canonical, slug, concept_id, concept_type }`.

---

### merge_concepts_tool

Merge one concept into another. All aliases of the source concept are re-mapped to the target. Paper counts are combined.

**MCP name:** `merge_concepts_tool`

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `from_id` | string | yes | — | Concept ID or slug to merge from |
| `to_id` | string | yes | — | Concept ID or slug to merge into |
| `reason` | string | no | `""` | Reason for merge (stored in merge history) |

**Returns:** `dict` — `{ merged: bool, from_slug, to_slug, aliases_remapped: int }`.

---

### list_concepts_tool

List concepts from the canonical registry.

**MCP name:** `list_concepts_tool`

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `concept_type` | string | no | `null` | Filter by type: `"concept"`, `"method"`, `"topic"` |
| `min_paper_count` | int | no | `0` | Return only concepts cited by at least this many papers |

**Returns:** `list[dict]` — each item has `concept_id`, `slug`, `canonical`, `concept_type`, `paper_count`, `alias_count`.

---

### reconcile_maintenance

Run lint + stats, then generate deduplicated maintenance tasks. Bridge between pure-read analysis and the actionable maintenance queue.

**MCP name:** `reconcile_maintenance`

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `auto_confirm` | bool | no | `true` | Auto-confirm tasks that meet merge rules (slug match, abbreviation whitelist, spelling variant) |

**Returns:** `dict` — `{ tasks_created: int, tasks_auto_confirmed: int, tasks_pending_review: int }`.

---

### get_maintenance_queue

View maintenance tasks in the queue.

**MCP name:** `get_maintenance_queue`

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `task_type` | string | no | `null` | Filter: `merge_candidate`, `promote_to_topic`, `stale_topic_refresh`, `orphan_fix`, `missing_concept_stub` |
| `status` | string | no | `null` | Filter: `pending`, `confirmed`, `processing`, `done`, `rejected` |

**Returns:** `list[dict]` — each item has `task_id`, `task_type`, `payload`, `status`, `confidence`, `created_at`.

---

### resolve_maintenance_task

Confirm, reject, or complete a maintenance task.

**MCP name:** `resolve_maintenance_task`

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `task_id` | int | yes | — | Task ID from the maintenance queue |
| `action` | string | no | `"confirm"` | `"confirm"`, `"reject"`, or `"complete"` |
| `reason` | string | no | `""` | Optional reason (stored for rejections) |

**Returns:** `dict` — `{ task_id, previous_status, new_status, action }`.

---

### export_db_state

Export authority-layer database tables to JSON for backup. The rebuildable index layer (`compile_state`, `compile_deps`) is excluded.

**MCP name:** `export_db_state`

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| *(none)* | | | | |

**Returns:** `dict` — `{ concept_registry: [...], concept_aliases: [...], concept_merge_history: [...], maintenance_queue: [...] }`.

---

### backfill_registry

Populate the concept registry from existing wiki frontmatter. Scans `wiki/concepts/`, `wiki/methods/`, and `wiki/papers/`. Does not create Compile IR (that requires LLM).

**MCP name:** `backfill_registry`

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| *(none)* | | | | |

**Returns:** `dict` — `{ concepts_registered: int, methods_registered: int, papers_indexed: int, compile_states_created: int }`.

---

### paper-distill-extract

Validate and persist an Extract-stage IR. Writes to `.state/ir/{citekey}.json`.

**MCP name:** `paper-distill-extract`

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `citekey` | string | yes | — | Paper citekey matching the source evidence file |
| `ir_json` | dict | yes | — | IR dict. Must include: `citekey`, `title`, `authors`, `tension_fields`, `candidate_concepts` |

**Returns:** `dict` — `{ path, schema_version, valid: bool, errors: [...] }`.

See [Compile IR Schema](compile-ir-schema.md) for full field documentation.

---

### knowledge-compile-resolve

Entity-link `candidate_concepts` in raw IRs against the concept registry. Pure Python — no LLM calls. Reads `{citekey}.json`, writes `{citekey}_resolved.json`.

**MCP name:** `knowledge-compile-resolve`

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `citekeys` | list[string] | yes | — | Citekeys to resolve |

**Returns:** `list[dict]` — each item: `{ citekey, resolved: bool, concepts_resolved: int, concepts_registered: int, path }`.

---

### knowledge-compile-publish

Write compiled markdown and atomically update `compile_state`/`compile_deps`. This is the EDC Write stage's sole exit point. Detects manual-edit conflicts via `content_hash`.

**MCP name:** `knowledge-compile-publish`

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `page_id` | string | yes | — | Citekey or article slug |
| `page_type` | string | yes | — | `paper`, `concept`, `method`, `topic`, `query` |
| `content` | string | yes | — | Full compiled Markdown content (including manually preserved sections) |
| `frontmatter` | dict | yes | — | YAML frontmatter to write |
| `ir_path` | string | no | `null` | Path to the resolved IR file (relative to vault) |
| `deps` | list[dict] | no | `null` | Compile dependencies: `[{ dep_id, dep_type }]` |

**Returns:** `dict` — `{ path, compile_version, content_hash, manual_edit_conflict: bool }`.

**Note:** If `manual_edit_conflict: true` is returned, stop immediately and report to the user. Do not overwrite.

---

### knowledge-compile-status

Get the compile state record for a wiki page.

**MCP name:** `knowledge-compile-status`

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `page_id` | string | yes | — | Citekey or article slug |
| `page_type` | string | no | `"paper"` | `paper`, `concept`, `method`, `topic`, `query` |

**Returns:** `dict` — `{ page_id, page_type, compile_version, schema_version, compiled_at, ir_path, content_hash, has_manual_edits }`.

---

### execute_maintenance_task

Execute a confirmed maintenance task through the Phase 3 controller.

**MCP name:** `execute_maintenance_task`

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `task_id` | int | yes | — | Task ID with status `confirmed` |

**Supported task types:** `merge_candidate` → executes concept merge; `promote_to_topic` → creates topic page; `stale_topic_refresh` → refreshes topic coverage.

**Returns:** `dict` — `{ task_id, task_type, success: bool, actions_taken: [...] }`.

---

### enqueue_maintenance_task

Explicitly create a maintenance task for later adjudication.

**MCP name:** `enqueue_maintenance_task`

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `task_type` | string | yes | — | `merge_candidate`, `promote_to_topic`, `stale_topic_refresh`, `orphan_fix`, `missing_concept_stub` |
| `payload` | dict | yes | — | Task-specific data (e.g., `{ from_slug, to_slug }` for merge) |
| `confidence` | float | no | `1.0` | Confidence score (0.0–1.0) |
| `status` | string | no | `"pending"` | Initial status |
| `auto_confirm` | bool | no | `false` | Immediately confirm if auto-merge rules match |

**Returns:** `dict` — `{ task_id, status, auto_confirmed: bool }`.

---

## Idea Tools

### idea-discover

Analyze the vault's concept-paper graph to find structural research gaps. Returns condensed gap lists for qualitative idea generation.

**MCP name:** `idea-discover`

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `user_topics` | list[string] | no | `null` | Filter analysis to specific topic keys |

**Returns:** `dict` — `{ methodology_mismatches: [...], combination_opportunities: [...], recurring_problems: [...], scaling_questions: [...], graph_stats: { node_count, edge_count, cluster_count } }`.

**Note:** Must be called first in every ideation session. `idea-trigger-candidates` is a subset view of this output.

---

### idea-tension-signals

Aggregate tension signals from all resolved Compile IRs.

**MCP name:** `idea-tension-signals`

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `min_occurrence` | int | no | `2` | Minimum number of papers a signal must appear in |
| `topic` | string | no | `null` | Filter to a specific topic key |

**Returns:** `dict` — `{ recurring_limitations: [...], all_assumptions: [...], open_question_clusters: [...], negative_results: [...] }`.

---

### idea-trigger-candidates

Return advanced trigger candidates for maintenance and ideation. Narrowed view over `idea-discover` focused on high-signal patterns.

**MCP name:** `idea-trigger-candidates`

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `user_topics` | list[string] | no | `null` | Filter to specific topic keys |

**Returns:** `dict` — `{ contradiction_candidates: [...], recurring_limitation_spikes: [...], cross_cluster_bridges: [...], benchmark_evaluation_splits: [...] }`.

**Note:** This is a subset of `idea-discover` output. Call `idea-discover` first.
