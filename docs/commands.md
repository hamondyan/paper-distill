# Commands

Paper Distill v3.0 keeps slash commands for business actions only.

- `/discover` writes inbox stubs.
- `/approve` marks selected inbox stubs approved without opening the inbox.
- `/inbox` summarizes pending and approved candidates.
- `/ingest approved` or `/ingest <ref>` captures raw evidence from approved inbox notes or agent-resolved natural references.
- `/lint` runs v3 health checks.

Read/index tasks belong to QMD CLI. Use [docs/qmd-cli.md](qmd-cli.md) for `qmd query`, `qmd get`, `qmd status`, `qmd update`, `qmd embed -f`, collection/context checks, and `qmd ls`.

## Tool Mapping

- `/discover` -> `discover_papers`
- `/approve` -> `approve_papers`
- `/inbox` -> no tool; it is a read-only summary and approval reminder
- `/ingest` -> `ingest_and_read`
- `/lint` -> `lint_vault`

## Command Details

### `/discover`

Runs discovery using configured topics or a user-supplied query, scores candidates, deduplicates against `.state/seen_papers.json`, and writes inbox stubs. It does not ingest.

### `/approve`

Marks matching inbox notes with a plain `#approved` body marker. It accepts paper IDs, arXiv IDs, exact titles, inbox paths, or `all` when the user clearly approves every pending inbox candidate.

This is the chat-native approval path. After the agent recommends papers, the user can say which ones to approve; the agent resolves that selection to the recommended paper IDs or inbox paths and calls `approve_papers`. Approval does not ingest. Use `/ingest approved` when ready to capture the approved notes.

Examples:

```text
/approve arxiv:1706.03762
/approve 1706.03762, 2410.24164
/approve all
```

### `/inbox`

Summarizes inbox notes and explains approval. Approval is file-native: add a plain `#approved` tag to the inbox note body.

### `/ingest`

Use `/ingest approved` to ingest approved inbox notes.

For direct paper intake, the agent can accept arXiv URLs, arXiv IDs, arXiv DOI values, exact titles, acronyms, aliases, project names, or mixed multi-paper requests. Natural references are resolved by the agent before calling the MCP tool. The MCP tool itself captures only resolved arXiv identities such as arXiv URLs, arXiv IDs, or arXiv DOI values.

For mixed direct intake, report resolved arXiv inputs separately from unresolved user references. That makes it clear which papers were eligible for capture and which names still need lookup.

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
