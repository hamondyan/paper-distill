from __future__ import annotations

import ast
from pathlib import Path


def test_server_entrypoint_is_thin_and_domain_registered() -> None:
    path = Path(__file__).resolve().parents[1] / "server/server.py"
    source = path.read_text(encoding="utf-8")
    tree = ast.parse(source)

    import_specs: list[tuple[str | None, tuple[str, ...]]] = []
    call_names: list[str] = []
    function_names: list[str] = []
    for node in tree.body:
        if isinstance(node, ast.ImportFrom):
            import_specs.append((node.module, tuple(alias.name for alias in node.names)))
        if isinstance(node, ast.Expr) and isinstance(node.value, ast.Call):
            func = node.value.func
            if isinstance(func, ast.Name):
                call_names.append(func.id)
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            function_names.append(node.name)
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

    assert set(import_specs) == {
        ("__future__", ("annotations",)),
        ("fastmcp", ("FastMCP",)),
        ("server.tools_core", ("register_core_tools",)),
        ("server.tools_intake", ("register_intake_tools",)),
        ("server.tools_knowledge", ("register_knowledge_tools",)),
        ("server.tools_health", ("register_health_tools",)),
    }
    assert set(call_names) == {
        "register_core_tools",
        "register_intake_tools",
        "register_knowledge_tools",
        "register_health_tools",
    }
    assert not any(name in source for name in forbidden_names)
    assert function_names == ["main"]
