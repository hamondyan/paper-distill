# Commands

Paper Distill v3.0 keeps slash commands for business actions only.

- `/discover` writes inbox stubs.
- `/inbox` summarizes pending and approved candidates.
- `/ingest approved` or `/ingest <url>` captures raw evidence.
- `/lint` runs v3 health checks.

Read/index tasks belong to QMD CLI. Use [docs/qmd-cli.md](qmd-cli.md) for `qmd query`, `qmd get`, `qmd status`, `qmd update`, `qmd embed -f`, collection/context checks, and `qmd ls`.

## Tool Mapping

- `/discover` -> `discover_papers`
- `/inbox` -> no tool; it is a read-only summary and approval reminder
- `/ingest` -> `ingest_and_read`
- `/lint` -> `lint_vault`

## Command Details

### `/discover`

Runs discovery using configured topics or a user-supplied query, scores candidates, deduplicates against `.state/seen_papers.json`, and writes inbox stubs. It does not ingest.

### `/inbox`

Summarizes inbox notes and explains approval. Approval is file-native: add a plain `#approved` tag to the inbox note body.

### `/ingest`

Use `/ingest approved` to ingest approved inbox notes.

For direct paper intake, the agent can accept arXiv URLs, arXiv IDs, arXiv DOI values, exact titles, acronyms, aliases, project names, or mixed multi-paper requests. Natural references are resolved by the agent to arXiv URLs before calling the MCP tool. The MCP tool captures only resolved arXiv identities.

Examples:

```text
/ingest approved
/ingest https://arxiv.org/abs/2410.24164
/ingest 10.48550/arxiv.2410.24164
/ingest 1706.03762
/ingest openvla, octo, diffusion policy
```

### `/lint`

Runs `lint_vault` and reports structural issues without rewriting files.
