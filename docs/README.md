# Paper Distill Docs

Paper Distill is an Obsidian-first, human-approved research knowledge system.

## Start Here

- [Installation](installation.md): install dependencies and start the MCP server.
- [Configuration](configuration.md): configure vault path, topics, search, capture, Zotero, and Obsidian CLI querying.
- [Commands](commands.md): user-facing slash commands and the MCP tools they map to.
- [Workflows](workflows.md): discovery, ingestion, compile, query, idea, memory, and maintenance flows.
- [Vault Layout](vault-layout.md): files and directories written inside the Obsidian vault.
- [Architecture](architecture.md): code structure, runtime boundaries, data contracts, and state layers.
- [Testing](testing.md): verification commands used for this repository.
- [Obsidian CLI Validation](obsidian-cli-validation.md): real-environment CLI and Bases validation.
- [TODO Status](todo.md): completion audit for the refactor checklist.

## Current Model

The visible knowledge path is:

```text
inbox -> sources/evidence -> wiki/papers -> wiki/concepts|methods|topics
```

Generated or intermediate machine state belongs under `.state/`. User-facing idea assets belong under `insights/ideas/`. Query and report assets belong under `insights/queries/`.
