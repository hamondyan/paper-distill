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
    legacy_runtime_name = "server" + "_" + "runtime"
    upsert_name = "upsert" + "_" + "wiki" + "_" + "page" + "_" + "v3"
    alias_name = "check" + "_" + "concept" + "_" + "alias" + "_" + "v3"
    merge_name = "merge" + "_" + "concept" + "_" + "v3"
    lint_name = "lint" + "_" + "vault" + "_" + "v3"
    forbidden_names = {
        legacy_runtime_name,
        "_DELEGATED_ASYNC_NAMES",
        "_delegate_async",
        "_delegate_sync",
        "_SYNC_BINDINGS",
        "_ORIGINAL_BINDINGS",
        "_DELEGATED_WRAPPERS",
        upsert_name,
        alias_name,
        merge_name,
        lint_name,
    }

    allowed_imports = {
        ("__future__", ("annotations",)),
        ("fastmcp", ("FastMCP",)),
        ("server.tools_health", ("register_health_tools",)),
        ("server.tools_intake", ("register_intake_tools",)),
        ("server.tools_knowledge", ("register_knowledge_tools",)),
        ("logging", None),
        ("pathlib", ("Path",)),
        ("server.config", ("ConfigError", "get_vault_path")),
        ("server.v3_store", ("audit_wiki_schema",)),
    }
    for module, names in import_specs:
        assert (module, names) in allowed_imports or (module, None) in allowed_imports, (
            f"unexpected import: {module} -> {names}"
        )
    assert set(call_names) == {
        "register_health_tools",
        "register_intake_tools",
        "register_knowledge_tools",
    }
    assert "tools_core" not in source
    assert not any(name in source for name in forbidden_names)
    assert set(function_names) <= {"main", "_run_startup_audit"}
