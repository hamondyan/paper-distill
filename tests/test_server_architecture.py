from __future__ import annotations

import ast
from pathlib import Path


def test_server_entrypoint_is_thin_and_domain_registered() -> None:
    path = Path(__file__).resolve().parents[1] / "server/server.py"
    source = path.read_text(encoding="utf-8")
    tree = ast.parse(source)

    top_level_defs = [
        node
        for node in tree.body
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
    ]
    nonempty_lines = [line for line in source.splitlines() if line.strip()]
    forbidden_names = {
        "server_runtime",
        "_DELEGATED_ASYNC_NAMES",
        "_delegate_async",
        "_delegate_sync",
        "_SYNC_BINDINGS",
        "_ORIGINAL_BINDINGS",
        "_DELEGATED_WRAPPERS",
        "upsert_wiki_page_v3",
        "check_concept_alias_v3",
        "merge_concept_v3",
        "lint_vault_v3",
    }

    assert "from server.tools_core import register_core_tools" in source
    assert "from server.tools_intake import register_intake_tools" in source
    assert "from server.tools_knowledge import register_knowledge_tools" in source
    assert "from server.tools_health import register_health_tools" in source
    assert "register_core_tools(mcp)" in source
    assert "register_intake_tools(mcp)" in source
    assert "register_knowledge_tools(mcp)" in source
    assert "register_health_tools(mcp)" in source
    assert not any(name in source for name in forbidden_names)
    assert len(top_level_defs) <= 1
    assert len(nonempty_lines) < 40
