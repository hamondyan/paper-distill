"""Distillation v3 MCP tools."""
from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Any

from fastmcp import FastMCP

from server.config import ConfigError, get_vault_path
from server.v3_distill import distill_paper_v3, distill_papers_v3


def _vault_path_or_error() -> tuple[Path | None, dict[str, Any] | None]:
    try:
        vault_path = Path(get_vault_path())
    except ConfigError as exc:
        return None, {"ok": False, "error": str(exc), "warnings": []}
    return vault_path, None


async def distill_paper(
    input_value: str,
    distilled: dict | None = None,
) -> dict[str, Any]:
    vault_path, error = _vault_path_or_error()
    if error is not None:
        return error
    return await asyncio.to_thread(distill_paper_v3, vault_path, input_value, distilled)


async def distill_papers(items: list[dict]) -> dict[str, Any]:
    vault_path, error = _vault_path_or_error()
    if error is not None:
        return error
    return await asyncio.to_thread(distill_papers_v3, vault_path, items)


def register_distill_tools(mcp: FastMCP) -> None:
    mcp.tool(name="distill_paper")(distill_paper)
    mcp.tool(name="distill_papers")(distill_papers)
