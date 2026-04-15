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
import subprocess
import sys
from pathlib import Path

from server.config import get_vault_path
from server.qmd_runtime import ensure_qmd_ready
from server.v3_bootstrap import ensure_v3_layout
from server.server_runtime import (
    export_db_state,
    backfill_registry,
)


async def _bootstrap(args: argparse.Namespace) -> None:
    vault_path_raw = args.vault_path or get_vault_path()
    if not vault_path_raw:
        print("Error: VAULT_PATH not configured. Set it in settings.json or env.", file=sys.stderr)
        sys.exit(1)

    vault_path = Path(vault_path_raw)
    layout = ensure_v3_layout(vault_path)
    try:
        qmd = ensure_qmd_ready(vault_path)
    except (FileNotFoundError, subprocess.CalledProcessError) as exc:
        qmd = {
            "status": "not_ready",
            "reason": getattr(exc, "stderr", "").strip() or "qmd init failed",
        }
    if qmd.get("status") not in {None, "ready"}:
        print(json.dumps({"layout": layout, "qmd": qmd}, indent=2, ensure_ascii=False), file=sys.stderr)
        sys.exit(1)
    print(json.dumps({"layout": layout, "qmd": qmd}, indent=2, ensure_ascii=False))


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
