# Architecture

Paper Distill is organized around four layers:

```text
Markdown UI -> Obsidian Engine -> Hidden JSON/SQLite State -> MCP Tools
```

## Markdown UI

The user-facing vault is Markdown:

- `sources/evidence/` stores captured paper evidence.
- `wiki/papers/` stores canonical paper work pages.
- `wiki/concepts`, `wiki/methods`, and `wiki/topics` store reusable knowledge pages.
- `insights/queries` and `insights/ideas` store reusable research outputs.

## Obsidian Engine

Obsidian handles local reading, backlinks, tags, and property browsing. Paper Distill does not maintain generated dashboards; current machine-readable state comes from `query-library`.

`query-library` uses an Obsidian-first adapter:

1. Official Obsidian CLI provider through the built-in normalization adapter.
2. Filesystem scan fallback.

The response reports the selected provider and fallback state.

The native Obsidian CLI/Bases primitives are validated for visible vault
queries, but hidden `.state/` assets are intentionally outside the Obsidian
query contract. The CLI adapter only runs when `vault_path` matches an open
Obsidian vault; temporary or offline vaults fall back to filesystem scan.

## Hidden State

Hidden state is reserved for machine-facing data:

- `.state/ir/`: compile IR JSON.
- `.state/memory/`: memory event state.
- `.state/paper-distill.db`: concept registry, aliases, merge history, maintenance queue, and compile dependency state.

Legacy mutation queues and publish journals have been removed.

## MCP Server

The MCP entrypoint is `server/server.py`. It only initializes FastMCP and registers domain tools from four `*_tools.py` files. Business logic is split into focused modules.

### Domain tool registration modules

| File | Registered tools |
|------|-----------------|
| `server/library_tools.py` | `search_papers`, `resolve_metadata`, `zotero_add`, `zotero_search`, `fetch_pdf_text`, `score_papers`, `query-library`, `bootstrap-library`, `update_learned_preferences` |
| `server/source_tools.py` | `source-discover`, `source-ingest` |
| `server/knowledge_tools.py` | `wiki-lint`, `library-stats`, `upsert_wiki_article`, `register_concept_tool`, `resolve_concept_tool`, `merge_concepts_tool`, `list_concepts_tool`, `reconcile_maintenance`, `get_maintenance_queue`, `resolve_maintenance_task`, `export_db_state`, `backfill_registry`, `paper-distill-extract`, `knowledge-compile-resolve`, `knowledge-compile-publish`, `knowledge-compile-status`, `execute_maintenance_task`, `enqueue_maintenance_task` |
| `server/idea_tools.py` | `idea-discover`, `idea-tension-signals`, `idea-trigger-candidates` |

### Server module map

| Module | Responsibility |
|--------|---------------|
| `server/server.py` | Entry point; creates FastMCP instance; registers tools |
| `server/server_runtime.py` | Wire-up of tool functions; re-exports from sub-modules; functions with MCP circular-dep constraints |
| `server/paper_scoring.py` | Pure-computation scoring engine: text utilities, all `_score_*` functions, `_ACRONYM_MAP` |
| `server/paper_frontmatter.py` | Frontmatter dict builders for inbox, source evidence, wiki pages |
| `server/capture_settings.py` | Config-reading helpers: topics, capture options, Zotero runtime |
| `server/paper_identity.py` | Paper identification, deduplication, DOI extraction, PDF text parsing |
| `server/discovery_helpers.py` | Discovery: query construction, diversity cap, drift detection |
| `server/ingestion_helpers.py` | Ingestion path calculations and wiki body payload builder |
| `server/arxiv_capture.py` | arXiv/ar5iv HTML fetching and cleaning; `CleanedArxivDocument` dataclass |
| `server/compile_ir.py` | IR schema (`_REQUIRED_KEYS`), validation, `aggregate_tension_signals`, `commit_compile_result` |
| `server/idea_verification.py` | Knowledge graph traversal and tension signal aggregation for idea tools |
| `server/vault_ops.py` | Path helpers and citekey generation for vault file layout |
| `server/vault_query.py` | `query_vault_sync` — synchronous vault frontmatter scan |
| `server/vault_lint.py` | Deterministic health checks for `wiki-lint` |
| `server/obsidian_query.py` | Obsidian CLI adapter + filesystem fallback |
| `server/database.py` | SQLite schema and low-level CRUD for concept_registry, compile_state, maintenance_queue |
| `server/memory_runtime.py` | Memory event state management |
| `server/research_item.py` | `ResearchItem` dataclass — the shared paper entity contract |
| `server/paper_utils.py` | Cross-cutting paper field normalization (venue, arxiv_id, canonical URLs) |
| `server/config.py` | Settings loading, env-var overrides, and `_DEFAULT_PAPER_DISTILL_SETTINGS` |

## EDC Compile Pipeline

The **Extract → Resolve → Write** (EDC) pipeline is the structured path for wiki compilation.

```text
sources/evidence/{date}/{citekey}.md
       │
       ▼  (agent reads + builds IR)
paper-distill-extract(citekey, ir_json)
       │ writes
       ▼
.state/ir/{citekey}.json          ← Raw IR
       │
       ▼  (pure Python, no LLM)
knowledge-compile-resolve([citekeys])
       │ writes
       ▼
.state/ir/{citekey}_resolved.json ← Resolved IR (concepts linked to registry)
       │
       ▼  (agent writes compiled markdown)
knowledge-compile-publish(page_id, page_type, content, frontmatter, ir_path, deps)
       │ writes + updates SQLite
       ▼
wiki/papers/{citekey}.md          ← Canonical wiki page
paper-distill.db compile_state    ← content_hash, version, compiled_at
```

**Extract stage:** The agent reads source evidence and generates a structured IR dict containing `citekey`, `title`, `authors`, `tension_fields`, and `candidate_concepts`. The IR is submitted via `paper-distill-extract`.

**Resolve stage:** `knowledge-compile-resolve` maps every `candidate_concept` against the concept registry (registering new concepts as needed) and writes `_resolved.json`. This is deterministic — no LLM involved.

**Write stage:** `knowledge-compile-publish` is the only exit point for EDC writes. It records a `content_hash` in SQLite and detects manual-edit conflicts. Unlike `upsert_wiki_article`, it updates `compile_state`.

## Scoring Formula

Papers are scored with a weighted sum of nine factors. Default weights (from `_DEFAULT_PAPER_DISTILL_SETTINGS`):

| Factor | Weight | What it measures |
|--------|--------|-----------------|
| `topic_fit` | 0.40 | Keyword overlap with configured topics |
| `recency` | 0.20 | Publication date (exponential decay) |
| `novelty` | 0.15 | Inverse of existing library coverage |
| `impact` | 0.10 | Citation count (log-scaled) |
| `venue_tier` | 0.07 | Tier-S / Tier-A venue membership |
| `author_preference` | 0.05 | Whitelist author match |
| `metadata_quality` | 0.03 | Completeness of title/abstract/DOI |

The `keyword_alignment` and `rejected_keywords` sub-scores further adjust `topic_fit`. Weights are configurable under `paper_distill.scoring.weights`.

## Concept Registry

The concept registry in `paper-distill.db` separates two concerns:

- **Registry entry:** a canonical concept slug with aliases, concept type, and paper count. Created automatically during the Resolve stage of EDC.
- **Wiki stub page:** a Markdown file under `wiki/concepts/{slug}.md`. Created by the agent following the **two-paper rule**: only after `list_concepts_tool(min_paper_count=2)` confirms the concept appears in two or more papers.

Registry entry exists ≠ wiki page exists. This is intentional — the registry is a bookkeeping table, not a content system.

Three auto-merge rules run during `register_concept_tool` and `reconcile_maintenance`:

1. **Slug match:** `"diffusion policy"` and `"diffusion-policy"` resolve to the same slug.
2. **Abbreviation whitelist:** entries in `concept_registry.abbreviation_whitelist` (e.g., `vla → vision-language-action`) trigger automatic merges.
3. **Spelling variants:** minor edit-distance differences are flagged as merge candidates.

## Data Contracts

- `ResearchItem` is the shared lightweight paper entity contract (title, authors, year, venue, citekey).
- Source evidence frontmatter is written from the paper contract plus capture metadata.
- Wiki paper frontmatter includes `page_state`, `confidence`, `last_compiled_at`, and `manual_notes_present`.
- Idea notes carry `idea_state`, `decision_reason`, `decision_at`, and `superseded_by`.
- IR files follow the schema documented in [Compile IR Schema](compile-ir-schema.md).
