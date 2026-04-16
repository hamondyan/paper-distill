# Testing

## v3 Verification

Run:

```bash
uv run pytest -q
uv run python -m compileall -q server tests
```

## Focused Documentation Checks

Run:

```bash
uv run pytest tests/test_v3_commands.py tests/test_no_retired_names.py tests/test_skill_inventory.py tests/test_v3_conversations.py -q
```

## Business MCP Smoke Check

```bash
uv run python - <<'PY'
import asyncio
from server.server import mcp

async def main():
    tools = await mcp.list_tools()
    names = sorted(tool.name for tool in tools)
    required = {
        "discover_papers",
        "ingest_and_read",
        "check_concept_alias",
        "upsert_wiki_page",
        "merge_concept",
        "lint_vault",
    }
    missing = sorted(required - set(names))
    if missing:
        raise SystemExit(f"missing tools: {missing}")
    print(f"tool_count={len(names)}")

asyncio.run(main())
PY
```

This smoke check should stay on the six-tool business surface only.

## CLI-Native QMD Checks

Use runtime help as the command authority:

```bash
qmd --help
qmd query "test"
qmd get path/to/file.md
qmd status
```
