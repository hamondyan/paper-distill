"""Knowledge v3 MCP tools."""
from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Any

from fastmcp import FastMCP

from server.config import get_vault_path
from server.qmd_runtime import qmd_reembed_force, qmd_update
from server.v3_alias import check_concept_alias_v3
from server.v3_health import merge_concept_v3
from server.v3_store import upsert_wiki_page_v3


def _vault_path_or_error() -> tuple[Path | None, dict[str, Any] | None]:
    vault_path = str(get_vault_path()).strip()
    if not vault_path:
        return None, {"ok": False, "error": "VAULT_PATH not configured."}
    return Path(vault_path), None


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
            "error": "VAULT_PATH not configured.",
            "exists": False,
            "canonical": name,
        }
    return await asyncio.to_thread(check_concept_alias_v3, vault_path, name)


async def merge_concept(old: str, new: str) -> dict[str, Any]:
    vault_path, error = _vault_path_or_error()
    if error is not None:
        return {"ok": False, "error": "VAULT_PATH not configured.", "warnings": []}
    return await asyncio.to_thread(merge_concept_v3, vault_path, old, new)


async def kb_update_index() -> dict[str, Any]:
    vault_path, error = _vault_path_or_error()
    if error is not None:
        return error
    return await asyncio.to_thread(qmd_update, vault_path)


async def kb_reembed_force() -> dict[str, Any]:
    vault_path, error = _vault_path_or_error()
    if error is not None:
        return error
    return await asyncio.to_thread(qmd_reembed_force, vault_path)


def register_knowledge_tools(mcp: FastMCP) -> None:
    mcp.tool(name="upsert_wiki_page")(upsert_wiki_page)
    mcp.tool(name="check_concept_alias")(check_concept_alias)
    mcp.tool(name="merge_concept")(merge_concept)
    mcp.tool(name="kb_update_index")(kb_update_index)
    mcp.tool(name="kb_reembed_force")(kb_reembed_force)
