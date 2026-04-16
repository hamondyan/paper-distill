# Commands

Paper Distill v3.0 exposes a small command surface.

- `/discover` writes inbox stubs.
- `/inbox` summarizes pending and approved candidates.
- `/ingest approved` or `/ingest <url>` captures raw evidence.
- `/search` uses `kb_search`.
- `/get` uses `kb_get`.
- `/lint` runs v3 health checks.
- `/status` reports readiness and qmd state.

## Tool Mapping

- `/discover` -> `discover_papers`
- `/ingest` -> `ingest_and_read`
- `/search` -> `kb_search`
- `/get` -> `kb_get`
- `/lint` -> `lint_vault`
- `/status` -> `status`

## Command Details

### `/discover`

Runs discovery using configured topics or a user-supplied query, scores candidates, deduplicates against `.state/seen_papers.json`, and writes inbox stubs. It does not ingest.

### `/inbox`

Summarizes inbox notes and explains approval. Approval is file-native: add a plain `#approved` tag to the inbox note body.

### `/ingest`

Use `/ingest approved` to ingest approved inbox notes. Use `/ingest <arXiv URL>` or `/ingest <arXiv DOI>` for direct capture.

Examples:

```text
/ingest approved
/ingest https://arxiv.org/abs/2410.24164
/ingest 10.48550/arxiv.2410.24164
```

### `/search`

Uses `kb_search` and qmd. The default scope is `canon`; use `insights` or `raw` only when the user explicitly asks for those layers.

### `/get`

Uses `kb_get` when the user already knows the paper ID, stable filename, or vault-relative Markdown path.

### `/lint`

Runs `lint_vault` and reports structural issues without rewriting files.

### `/status`

Runs layout bootstrap and qmd readiness checks. The qmd state is `ready`, `degraded`, or `not_ready`.
