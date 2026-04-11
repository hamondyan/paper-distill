from __future__ import annotations

import ast
from pathlib import Path


def test_server_entrypoint_is_thin_and_domain_registered() -> None:
    path = Path("server/server.py")
    source = path.read_text(encoding="utf-8")
    tree = ast.parse(source)

    top_level_defs = [
        node
        for node in tree.body
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
    ]
    nonempty_lines = [line for line in source.splitlines() if line.strip()]

    assert "from server.library_tools import register_library_tools" in source
    assert "from server.source_tools import register_source_tools" in source
    assert "from server.knowledge_tools import register_knowledge_tools" in source
    assert "from server.idea_tools import register_idea_tools" in source
    assert "register_library_tools(mcp)" in source
    assert "register_source_tools(mcp)" in source
    assert "register_knowledge_tools(mcp)" in source
    assert "register_idea_tools(mcp)" in source
    assert len(top_level_defs) <= 3
    assert len(nonempty_lines) < 220
