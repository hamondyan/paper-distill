# Paper Distill

Paper Distill v3.0 is a Markdown-first research knowledge system for paper discovery, approved ingestion, qmd-backed retrieval, and agent-safe knowledge writes.

## v3.0 Rules

- `qmd` is a hard dependency in v3.0.
- Formal read paths are `kb_search` and `kb_get`.
- Python tools own deterministic writes, validation, and index scheduling.
- Markdown files are the source of truth.
- The first-release workflow is `discover -> approve -> ingest -> search/get -> lint -> status`.

## Core Flow

```text
/discover -> add #approved in inbox note -> /ingest approved -> /search or /get -> /lint -> /status
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
- `/search` uses `kb_search`.
- `/get` uses `kb_get`.
- `/lint` runs v3 health checks.
- `/status` reports readiness and qmd state.

## Documentation

- [Installation](docs/installation.md)
- [Commands](docs/commands.md)
- [Architecture](docs/architecture.md)
- [Testing](docs/testing.md)
