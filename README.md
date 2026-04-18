# Paper Distill

Paper Distill v3.0 is a Markdown-first research knowledge system for paper discovery, approved ingestion, QMD-backed retrieval, and agent-safe knowledge writes.

## Quickstart

1. Install dependencies:

```bash
uv sync
```

2. Configure `settings.json` with an absolute `paper_distill.vault_path`. If this checkout already has `settings.json`, edit it directly; otherwise copy `settings.example.json` first:

```bash
cp settings.example.json settings.json
```

3. Check the local command entrypoints:

```bash
uv run paper-distill-admin --help
qmd --help
```

4. Bootstrap the vault layout and QMD mappings:

```bash
uv run paper-distill-admin bootstrap
```

5. Run the first workflow:

```text
/discover -> /approve <paper id or path> -> /ingest approved -> qmd query "your topic"
```

When installed as a namespaced plugin, the slash commands may appear with the plugin prefix, for example `/paper-distill:discover`.

Bootstrap succeeds when the command reports the vault layout plus ready QMD collections. If QMD retrieval looks stale after write-heavy work, run `qmd update`; run `qmd embed -f` when semantic search must reflect the new state immediately.

## v3.0 Rules

- `qmd` is a hard dependency in v3.0.
- Use qmd as the read/index path.
- Paper Distill business MCP tools own discovery, approved ingest, deterministic writes, and linting.
- Markdown files are the source of truth.
- The normal workflow is `discover -> approve -> ingest -> qmd query/get -> write -> lint`.

## Core Flow

```text
/discover -> approve in chat -> /ingest approved -> qmd query or qmd get -> write -> /lint
```

Direct ingestion is also available. The agent can resolve paper titles, acronyms, aliases, project names, arXiv URLs, arXiv IDs, or arXiv DOI values to arXiv identities, then call the single intake tool:

```text
/ingest https://arxiv.org/abs/2410.24164
/ingest 10.48550/arxiv.2410.24164
/ingest 1706.03762
/ingest openvla, octo, diffusion policy
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
- `/approve` marks selected inbox stubs approved from chat or explicit paper IDs/paths.
- `/ingest approved` or `/ingest <ref>` captures raw evidence from approved inbox notes or agent-resolved natural references.
- `/lint` runs v3 health checks.
- `/status` returns a vault health snapshot (counts, pending approvals, lint issues, last activity).

Some hosts expose plugin commands with the plugin namespace, such as `/paper-distill:ingest`.

For QMD read/index work, use [docs/qmd-cli.md](docs/qmd-cli.md).

## Documentation

- [Installation](docs/installation.md)
- [QMD CLI Guide](docs/qmd-cli.md)
- [Commands](docs/commands.md)
- [Architecture](docs/architecture.md)
- [Testing](docs/testing.md)
