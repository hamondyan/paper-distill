# Testing

## v3 Verification

Run:

```bash
uv run --with pytest python -m pytest -q
uv run python -m compileall -q server tests
```

## Focused Documentation Checks

Run:

```bash
uv run --with pytest python -m pytest tests/test_v3_commands.py tests/test_no_retired_names.py tests/test_skill_inventory.py tests/test_v3_conversations.py -q
```

## Cross-Host Plugin Layout Checks

Run:

```bash
uv run --with pytest python -m pytest tests/test_plugin_layout.py tests/test_v3_commands.py tests/test_skill_inventory.py tests/test_no_retired_names.py -q
```

## Repo-Local Marketplace Check

Run:

```bash
uv run --with pytest python -m pytest tests/test_plugin_layout.py -q
```

This check covers the root-as-plugin manifests, hook launch path, and the repo-local marketplace entry that points at `./plugins/paper-distill`.

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
        "distill_paper",
        "distill_papers",
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

This smoke check should stay on the business surface only.

## CLI-Native QMD Checks

Use runtime help as the command authority:

```bash
qmd --help
qmd query "test"
qmd get path/to/file.md
qmd status
```

## Common Failures

- If `uv run pytest -q` fails with `Failed to spawn: pytest`, use `uv run python -m pytest -q`.
- If `qmd --help` fails, install or expose the QMD binary before bootstrapping.
- If tools report a missing `settings.json`, copy `settings.example.json` to `settings.json` and set an absolute `paper_distill.vault_path`.
- If `qmd query` does not show recent writes, run `qmd update`; run `qmd embed -f` when semantic retrieval must be fresh immediately.
