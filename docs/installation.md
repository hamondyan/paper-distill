# Installation

## Requirements

- Python 3.10 or newer.
- `uv` for dependency and command execution.
- `qmd` installed on the machine.
- A configured vault path.

## Install Dependencies

```bash
uv sync
```

## Configure The Vault Path

Copy the example settings file:

```bash
cp settings.example.json settings.json
```

Set the absolute vault path:

```json
{
  "paper_distill": {
    "vault_path": "/absolute/path/to/your/vault"
  }
}
```

`settings.json` is the only runtime configuration source. Environment-variable overrides are not supported.
If this checkout already has a `settings.json`, edit that file directly instead of copying over it.

## Verify Local Commands

Confirm the Paper Distill admin entrypoint and QMD are both available:

```bash
uv run paper-distill-admin --help
qmd --help
```

`paper-distill-admin --help` should list the `bootstrap` subcommand. `qmd --help` should list commands such as `query`, `get`, `status`, `update`, and `embed`.

## Empty Vault Bootstrap

Run the bootstrap helper:

```bash
uv run paper-distill-admin bootstrap
```

`paper-distill-admin bootstrap` creates the vault layout and initializes the QMD collections and contexts used by Paper Distill.
It succeeds when the output reports the created layout entries and ready QMD collections.

## QMD Collections And Contexts

The bootstrap path is responsible for these repo mappings:

```bash
qmd collection add <vault>/wiki/papers --name canon-papers
qmd collection add <vault>/wiki/concepts --name canon-concepts
qmd collection add <vault>/insights/conversations --name insights-conversations
qmd collection add <vault>/insights/ideas --name insights-ideas
qmd collection add <vault>/raw/evidence --name raw-evidence
qmd context add qmd://canon-papers "Canonical distilled papers"
qmd context add qmd://canon-concepts "Canonical concept pages"
qmd context add qmd://insights-conversations "Conversation-derived research insights"
qmd context add qmd://insights-ideas "Idea drafts and later validation assets"
qmd context add qmd://raw-evidence "Raw captured evidence and source markdown"
```

After bootstrap, use [docs/qmd-cli.md](qmd-cli.md) for day-to-day read/index work.

## Start The MCP Server

```bash
uv run paper-distill-server
```
