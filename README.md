# Paper Distill

Paper Distill v3.0 is a Markdown-first research knowledge system for paper discovery, approved ingestion, QMD-backed retrieval, and agent-safe knowledge writes.

## v3.0 Rules

- `qmd` is a hard dependency in v3.0.
- Use qmd as the read/index path.
- Paper Distill business MCP tools own discovery, approved ingest, deterministic writes, and linting.
- Markdown files are the source of truth.
- The normal workflow is `discover -> approve -> ingest -> qmd query/get -> write -> lint`.

## Core Flow

```text
/discover -> add #approved in inbox note -> /ingest approved -> qmd query or qmd get -> write -> /lint
```

Direct ingestion is also available for supported arXiv URLs and arXiv DOI values:

```text
/ingest https://arxiv.org/abs/2410.24164
/ingest 10.48550/arxiv.2410.24164
```

## Vault Shape

```text
vault/
├── inbox/
├── raw/evidence/
├── wiki/papers/
├── wiki/concepts/
├── insights/ideas/
├── insights/conversations/
├── exports/presentations/
├── vault-log.md
└── .state/
```

## Public Commands

- `/discover` writes inbox stubs.
- `/inbox` summarizes pending and approved candidates.
- `/ingest approved` or `/ingest <url>` captures raw evidence.
- `/lint` runs v3 health checks.

For QMD read/index work, use [docs/qmd-cli.md](docs/qmd-cli.md).

## Documentation

- [Installation](docs/installation.md)
- [QMD CLI Guide](docs/qmd-cli.md)
- [Commands](docs/commands.md)
- [Architecture](docs/architecture.md)
- [Testing](docs/testing.md)
