# Paper Distill Docs

Paper Distill is an Obsidian-friendly v3 research knowledge system for discovering papers, approving capture, searching with qmd, and maintaining canonical Markdown notes.

## Start Here

- [Installation](installation.md): install dependencies, configure the vault, and initialize qmd collections.
- [Commands](commands.md): user-facing slash commands and their MCP tools.
- [Architecture](architecture.md): storage layers, read/write surfaces, and readiness rules.
- [Configuration](configuration.md): settings and environment variables.
- [Vault Layout](vault-layout.md): directories created inside the vault.
- [Frontmatter Reference](frontmatter-reference.md): fields used by each managed note type.
- [Testing](testing.md): repository verification commands.

## Core Model

Markdown files are the durable knowledge layer. Python tools own deterministic writes, path safety, vault checks, qmd index updates, and capture repair.

```text
discover -> approve -> ingest -> search/get -> write -> lint -> status
```

The canonical wiki has two agent-owned areas: `wiki/papers/` and `wiki/concepts/`. Research ideas and distilled conversation notes are knowledge assets under `insights/ideas/` and `insights/conversations/`, and they are written through Python tools.
