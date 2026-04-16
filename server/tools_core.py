"""Core v3 MCP tools."""
from __future__ import annotations

from typing import Any

from fastmcp import FastMCP

from server.config import get_vault_path
from server.qmd_runtime import ensure_qmd_ready, qmd_get, qmd_ready_report, qmd_search
from server.v3_bootstrap import ensure_v3_layout


def _vault_path_or_error() -> tuple[str | None, dict[str, Any] | None]:
    vault_path = str(get_vault_path()).strip()
    if not vault_path:
        return None, {"status": "error", "error": "VAULT_PATH not configured."}
    return vault_path, None


async def kb_search(query: str, scope: str = "canon") -> dict[str, Any]:
    vault_path_value, error = _vault_path_or_error()
    if error is not None:
        return error

    from pathlib import Path

    vault_path = Path(vault_path_value)
    ensure_v3_layout(vault_path)
    return qmd_search(vault_path=vault_path, query=query, scope=scope)


async def kb_get(id_or_path: str) -> dict[str, Any]:
    vault_path_value, error = _vault_path_or_error()
    if error is not None:
        return error

    from pathlib import Path

    vault_path = Path(vault_path_value)
    ensure_v3_layout(vault_path)
    return qmd_get(vault_path=vault_path, id_or_path=id_or_path)


async def status() -> dict[str, Any]:
    vault_path_value, error = _vault_path_or_error()
    if error is not None:
        return error

    from pathlib import Path
    import subprocess

    vault_path = Path(vault_path_value)
    layout = ensure_v3_layout(vault_path)
    try:
        ensure_qmd_ready(vault_path)
    except (FileNotFoundError, subprocess.CalledProcessError):
        pass
    qmd = qmd_ready_report(vault_path)
    return {"layout": layout, "qmd": qmd}


def register_core_tools(mcp: FastMCP) -> None:
    mcp.tool(name="kb_search")(kb_search)
    mcp.tool(name="kb_get")(kb_get)
    mcp.tool(name="status")(status)
