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

The MCP entrypoint is `server/server.py`. It only initializes FastMCP and registers domain tools.

Domain tool modules:

- `server/library_tools.py`
- `server/source_tools.py`
- `server/knowledge_tools.py`
- `server/idea_tools.py`

Most business logic currently lives in `server/server_runtime.py` and focused support modules such as:

- `server/obsidian_query.py`
- `server/research_item.py`
- `server/compile_ir.py`
- `server/idea_verification.py`
- `server/memory_runtime.py`
- `server/vault_ops.py`
- `server/vault_lint.py`
- `server/database.py`

## Data Contracts

- `ResearchItem` is the shared lightweight paper entity contract.
- Source evidence frontmatter is written from the paper contract plus capture metadata.
- Wiki paper frontmatter includes `page_state`, `confidence`, `last_compiled_at`, and `manual_notes_present`.
- Idea notes carry `idea_state`, `decision_reason`, `decision_at`, and `superseded_by`.
