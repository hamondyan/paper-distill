"""Paper Distill v3 MCP entrypoint."""
from __future__ import annotations

from fastmcp import FastMCP

from server.tools_core import register_core_tools
from server.tools_health import register_health_tools
from server.tools_intake import register_intake_tools
from server.tools_knowledge import register_knowledge_tools

mcp = FastMCP("paper-distill")

register_core_tools(mcp)
register_intake_tools(mcp)
register_knowledge_tools(mcp)
register_health_tools(mcp)


def main() -> None:
    mcp.run()


if __name__ == "__main__":
    main()
