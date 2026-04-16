"""Knowledge v3 MCP tools."""
from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Any

from fastmcp import FastMCP

from server.config import ConfigError, get_vault_path
from server.v3_alias import check_concept_alias_v3
from server.v3_health import merge_concept_v3
from server.v3_store import upsert_wiki_page_v3


def _vault_path_or_error() -> tuple[Path | None, dict[str, Any] | None]:
    try:
        vault_path = Path(get_vault_path())
    except ConfigError as exc:
        return None, {"ok": False, "error": str(exc)}
    return vault_path, None


async def upsert_wiki_page(
    page_type: str,
    target: str,
    frontmatter: dict,
    body: str,
) -> dict[str, Any]:
    vault_path, error = _vault_path_or_error()
    if error is not None:
        return error
    return await asyncio.to_thread(
        upsert_wiki_page_v3,
        vault_path,
        page_type,
        target,
        frontmatter,
        body,
    )


async def check_concept_alias(name: str) -> dict[str, Any]:
    vault_path, error = _vault_path_or_error()
    if error is not None:
        return {
            "ok": False,
            "error": error["error"],
            "exists": False,
            "canonical": name,
        }
    return await asyncio.to_thread(check_concept_alias_v3, vault_path, name)


async def merge_concept(old: str, new: str) -> dict[str, Any]:
    vault_path, error = _vault_path_or_error()
    if error is not None:
        return {"ok": False, "error": error["error"], "warnings": []}
    return await asyncio.to_thread(merge_concept_v3, vault_path, old, new)


def register_knowledge_tools(mcp: FastMCP) -> None:
    mcp.tool(name="upsert_wiki_page")(upsert_wiki_page)
    mcp.tool(name="check_concept_alias")(check_concept_alias)
    mcp.tool(name="merge_concept")(merge_concept)
