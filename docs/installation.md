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

You can also use:

```bash
export VAULT_PATH="/absolute/path/to/your/vault"
```

## Empty Vault Bootstrap

Run `/status` first. The v3 status path creates the required layout and checks qmd readiness.

## QMD Bootstrap

After installing `qmd`, initialize Paper Distill's collections once the vault layout exists:

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

The server also reconciles the expected qmd collections during `status`.

## Start The MCP Server

```bash
uv run paper-distill-server
```
