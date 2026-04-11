# Testing

## Full Test Suite

```bash
uv run pytest -q
```

## Import And Syntax Check

```bash
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
        "query-library",
        "source-discover",
        "source-ingest",
        "knowledge-compile-publish",
        "paper-distill-extract",
        "idea-discover",
    }
    missing = sorted(required - set(names))
    if missing:
        raise SystemExit(f"missing tools: {missing}")
    print(f"tool_count={len(names)}")

asyncio.run(main())
PY
```

## Package Build

```bash
uv build
```

## Current Verification Baseline

The repository has been verified with:

- `uv run pytest -q`
- `uv run python -m compileall -q server tests`
- MCP tool surface smoke check
- `uv build`
