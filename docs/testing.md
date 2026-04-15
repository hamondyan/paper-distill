# Testing

## v3 Verification

Run:

```bash
uv run pytest -q
uv run python -m compileall -q server tests
```

## MCP Surface Smoke Check

```bash
uv run python - <<'PY'
import asyncio
from server.server import mcp

async def main():
    tools = await mcp.list_tools()
    names = sorted(tool.name for tool in tools)
    required = {
        "status",
        "kb_search",
        "kb_get",
        "discover_papers",
        "ingest_and_read",
        "check_concept_alias",
        "upsert_wiki_page",
        "merge_concept",
    }
    missing = sorted(required - set(names))
    if missing:
        raise SystemExit(f"missing tools: {missing}")
    print(f"tool_count={len(names)}")

asyncio.run(main())
PY
```
