"""Paper Distill admin CLI — one-time setup and maintenance commands.

Usage:
    python -m server.cli bootstrap [--vault-path PATH]
    python -m server.cli export-db
    python -m server.cli backfill

These operations are NOT exposed as MCP tools because they are
rarely used and would clutter the agent's tool list.
"""
from __future__ import annotations

import argparse
import asyncio
import json
import sys

from server.server_runtime import (
    bootstrap_vault,
    export_db_state,
    backfill_registry,
)


async def _bootstrap(args: argparse.Namespace) -> None:
    result = await bootstrap_vault(vault_path=args.vault_path)
    if result.get("error"):
        print(f"Error: {result['error']}", file=sys.stderr)
        sys.exit(1)
    print(json.dumps(result, indent=2, ensure_ascii=False))


async def _export_db(args: argparse.Namespace) -> None:
    result = await export_db_state()
    if result.get("error"):
        print(f"Error: {result['error']}", file=sys.stderr)
        sys.exit(1)
    print(json.dumps(result, indent=2, ensure_ascii=False))


async def _backfill(args: argparse.Namespace) -> None:
    result = await backfill_registry()
    if result.get("error"):
        print(f"Error: {result['error']}", file=sys.stderr)
        sys.exit(1)
    print(json.dumps(result, indent=2, ensure_ascii=False))


def main() -> None:
    parser = argparse.ArgumentParser(
        prog="paper-distill-admin",
        description="Paper Distill admin utilities",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    p_boot = sub.add_parser("bootstrap", help="Initialize vault directory structure")
    p_boot.add_argument("--vault-path", default=None, help="Override vault path")
    p_boot.set_defaults(func=_bootstrap)

    p_export = sub.add_parser("export-db", help="Export authority-layer DB to JSON")
    p_export.set_defaults(func=_export_db)

    p_backfill = sub.add_parser("backfill", help="Populate concept registry from wiki")
    p_backfill.set_defaults(func=_backfill)

    args = parser.parse_args()
    asyncio.run(args.func(args))


if __name__ == "__main__":
    main()
