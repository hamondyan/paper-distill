# Installation

## Requirements

- Python 3.10 or newer.
- `uv` for dependency and command execution.
- An Obsidian vault path.
- Optional: Zotero credentials if using Zotero Web API mode.

## Install Dependencies

From the repository root:

```bash
uv sync
```

## Configure Your Vault

Copy the example settings file:

```bash
cp settings.example.json settings.json
```

Edit `settings.json` and set:

```json
{
  "paper_distill": {
    "vault_path": "/absolute/path/to/your/obsidian/vault"
  }
}
```

You can also use an environment variable:

```bash
export VAULT_PATH="/absolute/path/to/your/obsidian/vault"
```

## Start The MCP Server

```bash
uv run paper-distill-server
```

The bundled launcher uses the same entrypoint:

```bash
./scripts/run-mcp.sh
```

## Client Setup

Use the repository `.mcp.json` as the MCP client entry. Codex, Claude, and OpenClaw-style clients can launch the same server command.

If a client cannot resolve the repo path automatically, configure it to run:

```bash
uv --directory /absolute/path/to/paper-distill-v2 run paper-distill-server
```

## First Check

After setup, ask your agent to run:

```text
/status
```

If the vault has not been initialized yet, run a discovery or ingestion workflow. Paper Distill will create the `Paper Distill/` structure inside the configured vault.
