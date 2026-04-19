"""Paper Distill v3 MCP entrypoint."""
from __future__ import annotations

import logging
from pathlib import Path

from fastmcp import FastMCP

from server.config import ConfigError, get_vault_path
from server.tools_distill import register_distill_tools
from server.tools_health import register_health_tools
from server.tools_intake import register_intake_tools
from server.tools_knowledge import register_knowledge_tools
from server.v3_store import audit_wiki_schema

mcp = FastMCP("paper-distill")

register_intake_tools(mcp)
register_distill_tools(mcp)
register_knowledge_tools(mcp)
register_health_tools(mcp)


def _run_startup_audit() -> None:
    logger = logging.getLogger("paper_distill.startup")
    try:
        vault_path = Path(get_vault_path())
    except ConfigError as exc:
        logger.info("startup audit skipped: %s", exc)
        return
    if not vault_path.is_dir():
        logger.info("startup audit skipped: vault path %s does not exist", vault_path)
        return
    violations = audit_wiki_schema(vault_path)
    if not violations:
        return
    logger.warning(
        "wiki schema audit found %d non-compliant page(s); "
        "existing test data is untouched, but new writes must satisfy required fields",
        len(violations),
    )
    for item in violations:
        logger.warning(
            "  [%s] %s -> %s",
            item["page_type"],
            item["path"],
            "; ".join(item["errors"]),
        )


def main() -> None:
    _run_startup_audit()
    mcp.run()


if __name__ == "__main__":
    main()
