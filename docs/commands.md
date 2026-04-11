# Commands

Paper Distill supports natural-language use through an agent, plus slash-command style workflows.

## Paper Intake

- `/discover <query>`: search configured paper sources and write candidate inbox cards.
- `/search <query>`: alias for discovery.
- `/digest`: run daily discovery across configured topics.
- `/add-paper <doi|arxiv|url>`: directly ingest a user-approved paper.
- `/ingest <doi|arxiv|url>`: alias for direct ingestion.
- `/process-inbox`: ingest approved inbox notes.

## Knowledge Workbench

- `/compile`: refresh canonical wiki pages from source evidence and hidden IR.
- `/query <question>`: answer using the maintained library and save substantial results as query assets.
- `/lint`: run deterministic vault health checks.
- `/status`: report vault statistics.

## Ideas

- `/ideas`: analyze graph gaps and write/edit idea notes under `insights/ideas/`.

## Lightweight Preview

- `/summarize <doi|url>`: summarize a paper without adding it to the maintained vault.

## Key MCP Tools

- `query-library`
- `source-discover`
- `source-ingest`
- `knowledge-compile-resolve`
- `knowledge-compile-publish`
- `knowledge-compile-status`
- `idea-discover`
- `idea-tension-signals`
- `wiki-lint`
- `library-stats`
