# Paper Distill

Paper Distill is an Obsidian-first research knowledge system for paper discovery, evidence capture, wiki compilation, query synthesis, and idea generation.

It is built around one rule: papers only become long-term knowledge after a human approves them.

## What It Does

- Discovers candidate papers from arXiv, Semantic Scholar, OpenAlex, DBLP, and Papers with Code.
- Stages candidates in `Paper Distill/inbox/` for human approval.
- Captures approved papers into `Paper Distill/sources/evidence/`.
- Maintains canonical paper pages in `Paper Distill/wiki/papers/`.
- Compiles reusable wiki pages for concepts, methods, topics, and paper syntheses via the EDC pipeline (Extract → Resolve → Write).
- Saves substantive research answers into `Paper Distill/insights/queries/`.
- Writes research ideas as editable notes in `Paper Distill/insights/ideas/`.
- Supports Zotero handoff through `local_first`, `web_api`, or `disabled` modes.
- Exposes everything through 32 MCP tools for Claude, Codex, and compatible agents.

## Core Flow

```text
discover -> inbox approval -> sources/evidence -> wiki/papers -> query / ideas / compile
```

Directly approved papers can skip discovery:

```text
add-paper -> sources/evidence -> wiki/papers
```

## Common Usage

- Find papers: `/discover vision language action manipulation`
- Add a known paper: `/add-paper 10.48550/arxiv.2410.24164`
- Process approved inbox items: `/process-inbox`
- Ask the vault a research question: `/query what VLA architectures are in my library?`
- Refresh compiled knowledge: `/compile`
- Generate research ideas: `/ideas`
- Check vault health: `/lint`
- Preview one paper without ingestion: `/summarize <doi|url>`

## Vault Shape

```text
Paper Distill/
├── inbox/
├── sources/evidence/
├── wiki/papers/
├── wiki/concepts/
├── wiki/methods/
├── wiki/topics/
├── insights/queries/
├── insights/ideas/
├── memory/
├── zotero/imports/
└── .state/
    ├── ir/               ← Compile IR JSON
    ├── memory/           ← Memory event state
    └── paper-distill.db  ← Concept registry, compile state, maintenance queue
```

## MCP Tools (32 total)

| Domain | Tools |
|--------|-------|
| **Library** | `search_papers`, `resolve_metadata`, `zotero_add`, `zotero_search`, `fetch_pdf_text`, `score_papers`, `query-library`, `bootstrap-library`, `update_learned_preferences` |
| **Source** | `source-discover`, `source-ingest` |
| **Knowledge** | `wiki-lint`, `library-stats`, `upsert_wiki_article`, `register_concept_tool`, `resolve_concept_tool`, `merge_concepts_tool`, `list_concepts_tool`, `reconcile_maintenance`, `get_maintenance_queue`, `resolve_maintenance_task`, `export_db_state`, `backfill_registry`, `paper-distill-extract`, `knowledge-compile-resolve`, `knowledge-compile-publish`, `knowledge-compile-status`, `execute_maintenance_task`, `enqueue_maintenance_task` |
| **Idea** | `idea-discover`, `idea-tension-signals`, `idea-trigger-candidates` |

See [MCP Tool Reference](docs/mcp-tool-reference.md) for full parameter documentation.

## Documentation

- [Installation](docs/installation.md)
- [Configuration](docs/configuration.md)
- [Commands](docs/commands.md)
- [Workflows](docs/workflows.md)
- [Architecture](docs/architecture.md)
- [MCP Tool Reference](docs/mcp-tool-reference.md)
- [Frontmatter Reference](docs/frontmatter-reference.md)
- [Compile IR Schema](docs/compile-ir-schema.md)
- [Skill / Agent Boundary](docs/skill-agent-boundary.md)
- [Troubleshooting](docs/troubleshooting.md)
- [Vault Layout](docs/vault-layout.md)
- [Obsidian CLI Validation](docs/obsidian-cli-validation.md)
- [Testing](docs/testing.md)

## License

MIT
