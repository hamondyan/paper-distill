# Paper Distill Docs

Paper Distill is an Obsidian-friendly v3 research knowledge system for discovering papers, approving capture from chat, reading through QMD CLI, and maintaining canonical Markdown notes.

## Start Here

- [Installation](installation.md): install dependencies, configure the vault, and bootstrap the layout plus QMD collections/contexts.
- [QMD CLI](qmd-cli.md): canonical guide for read/index workflows in Paper Distill.
- [Commands](commands.md): business slash commands and their MCP tools.
- [Architecture](architecture.md): storage layers and the QMD CLI versus business MCP boundary.
- [Configuration](configuration.md): the required `settings.json` schema and field meanings.
- [Vault Layout](vault-layout.md): directories created inside the vault.
- [Frontmatter Reference](frontmatter-reference.md): fields used by each managed note type.
- [Testing](testing.md): repository verification commands.

## Core Model

Markdown files are the durable knowledge layer. QMD CLI owns read/index work. Python tools own deterministic writes, path safety, vault checks, and capture repair.

```text
discover -> approve -> ingest -> qmd query/get -> write -> lint
```

The canonical wiki has two agent-owned areas: `wiki/papers/` and `wiki/concepts/`. Research ideas and distilled conversation notes are knowledge assets under `insights/ideas/` and `insights/conversations/`, and they are written through Python tools.
