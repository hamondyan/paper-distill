# Client Support

Paper Distill now ships as a single MCP-backed bundle that can be used from Claude, Codex, and OpenClaw.

## Shared Runtime

All clients launch the same server through [../.mcp.json](/Users/huang/Desktop/paper-distill-v2/.mcp.json).

The server launcher is [../scripts/run-mcp.sh](/Users/huang/Desktop/paper-distill-v2/scripts/run-mcp.sh), which resolves the repo root and runs:

```bash
uv --directory <repo-root> run paper-distill-server
```

## Claude

- Manifest: [../.claude-plugin/plugin.json](/Users/huang/Desktop/paper-distill-v2/.claude-plugin/plugin.json)
- MCP config: [../.mcp.json](/Users/huang/Desktop/paper-distill-v2/.mcp.json)
- Hooks: [../hooks/hooks.json](/Users/huang/Desktop/paper-distill-v2/hooks/hooks.json)

## Codex

- Manifest: [../.codex-plugin/plugin.json](/Users/huang/Desktop/paper-distill-v2/.codex-plugin/plugin.json)
- MCP config: [../.mcp.json](/Users/huang/Desktop/paper-distill-v2/.mcp.json)
- Hooks: [../hooks/hooks.json](/Users/huang/Desktop/paper-distill-v2/hooks/hooks.json)
- Skills: [../skills](/Users/huang/Desktop/paper-distill-v2/skills)

## OpenClaw

OpenClaw can consume this repository through the compatible bundle layout:

- Claude bundle marker: [../.claude-plugin/plugin.json](/Users/huang/Desktop/paper-distill-v2/.claude-plugin/plugin.json)
- Codex bundle marker: [../.codex-plugin/plugin.json](/Users/huang/Desktop/paper-distill-v2/.codex-plugin/plugin.json)

In practice, OpenClaw can reuse the same MCP server, skills, commands, and agents that the other two clients use.

## Recommended Environment

- `VAULT_PATH`
- `OPENALEX_EMAIL`
- `S2_API_KEY`
- `ZOTERO_MODE`
- `ZOTERO_COLLECTION_NAME`
- `ZOTERO_LOCAL_EXPORT_DIR`
- `ZOTERO_LIBRARY_ID`
- `ZOTERO_API_KEY`

For `local_first` mode, only `VAULT_PATH` is required.
