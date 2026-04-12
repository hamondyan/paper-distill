# Commands

Paper Distill supports natural-language use through an agent and slash-command style workflows.

## Slash Command Quick Reference

| Command | Description | Underlying Skill |
|---------|-------------|-----------------|
| `/discover <query>` | Search configured sources and write candidate inbox cards | paper-intake |
| `/search <query>` | Alias for `/discover` | paper-intake |
| `/digest` | Daily discovery across all configured topics | paper-intake |
| `/add-paper <doi\|arxiv\|url>` | Directly ingest a user-approved paper | paper-intake |
| `/ingest <doi\|arxiv\|url>` | Alias for `/add-paper` | paper-intake |
| `/process-inbox` | Ingest all approved inbox notes | paper-intake |
| `/summarize <doi\|url>` | Summarize a paper without adding it to the vault | paper-intake |
| `/compile` | Refresh canonical wiki pages from evidence and hidden IR | knowledge-workbench |
| `/query <question>` | Answer a research question and save the result | knowledge-workbench |
| `/lint` | Run deterministic vault health checks | knowledge-workbench |
| `/status` | Report vault statistics | knowledge-workbench |
| `/ideas` | Analyze graph gaps and write/edit idea notes | idea-workbench |

## MCP Tool Complete Reference

32 tools across four domains. See [MCP Tool Reference](mcp-tool-reference.md) for full parameter documentation.

### Library Tools (9 tools)

| MCP Name | Function | Description |
|----------|----------|-------------|
| `search_papers` | `search_papers` | Search arXiv, Semantic Scholar, OpenAlex, DBLP, Papers with Code |
| `resolve_metadata` | `resolve_metadata` | Resolve full metadata for a DOI via CrossRef + Unpaywall |
| `zotero_add` | `zotero_add` | Add papers to Zotero with auto-metadata enrichment |
| `zotero_search` | `zotero_search` | Search existing papers in Zotero library |
| `fetch_pdf_text` | `fetch_pdf_text` | Fetch and extract text from an open-access paper (ar5iv HTML first, then PDF) |
| `score_papers` | `score_papers` | Score papers using the v2 topic-aware deterministic formula |
| `query-library` | `query_vault` | Query library metadata by parsing YAML frontmatter |
| `bootstrap-library` | `bootstrap_vault` | Initialize the Paper Distill directory structure |
| `update_learned_preferences` | `update_learned_preferences` | Atomically append accepted/rejected keywords and preferred venues to settings |

### Source Tools (2 tools)

| MCP Name | Function | Description |
|----------|----------|-------------|
| `source-discover` | `discover_papers` | Search, score, arXiv-bind, and save candidates to inbox |
| `source-ingest` | `source_ingest` | Persist approved evidence into `sources/`; modes: `approved_inbox`, `direct_identifier` |

### Knowledge Tools (18 tools)

| MCP Name | Function | Description |
|----------|----------|-------------|
| `wiki-lint` | `lint_vault` | Deterministic structural health checks |
| `library-stats` | `vault_stats` | Vault statistics: paper counts, compile rates, coverage |
| `upsert_wiki_article` | `upsert_wiki_article` | Safe one-off wiki write outside EDC (does not update compile_state) |
| `register_concept_tool` | `register_concept_tool` | Register a concept in the canonical registry |
| `resolve_concept_tool` | `resolve_concept_tool` | Resolve a surface form to its canonical concept |
| `merge_concepts_tool` | `merge_concepts_tool` | Merge one concept into another |
| `list_concepts_tool` | `list_concepts_tool` | List concepts; filterable by type and paper count |
| `reconcile_maintenance` | `reconcile_maintenance` | Run lint + stats and generate maintenance tasks |
| `get_maintenance_queue` | `get_maintenance_queue` | View maintenance tasks; filterable by type and status |
| `resolve_maintenance_task` | `resolve_maintenance_task` | Confirm, reject, or complete a maintenance task |
| `export_db_state` | `export_db_state` | Export concept_registry and maintenance_queue to JSON |
| `backfill_registry` | `backfill_registry` | Populate registry from existing wiki frontmatter |
| `paper-distill-extract` | `write_compile_ir` | Validate and persist Extract-stage IR to `.state/ir/` |
| `knowledge-compile-resolve` | `resolve_compile_ir` | Entity-link candidate_concepts against the registry (Resolve stage) |
| `knowledge-compile-publish` | `commit_compile_result` | Write compiled markdown and update compile_state (Write stage) |
| `knowledge-compile-status` | `get_compile_state` | Get compile state for a wiki page (version, hash, compiled_at) |
| `execute_maintenance_task` | `execute_maintenance_task` | Execute a confirmed maintenance task |
| `enqueue_maintenance_task` | `enqueue_maintenance_task` | Manually create a maintenance task |

### Idea Tools (3 tools)

| MCP Name | Function | Description |
|----------|----------|-------------|
| `idea-discover` | `analyze_knowledge_graph` | Analyze vault concept-paper graph for structural research gaps |
| `idea-tension-signals` | `query_tension_signals` | Aggregate tension signals from all resolved IRs |
| `idea-trigger-candidates` | `query_trigger_candidates` | Return focused trigger candidates (contradiction, bridge, benchmark split) |
