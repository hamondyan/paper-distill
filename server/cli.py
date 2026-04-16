"""Paper Distill admin CLI for v3 vault bootstrap."""
from __future__ import annotations

import argparse
import asyncio
import json
import subprocess
import sys
from pathlib import Path

from server.config import ConfigError, get_vault_path
from server.qmd_runtime import ensure_qmd_ready
from server.v3_bootstrap import ensure_v3_layout


async def _bootstrap(args: argparse.Namespace) -> None:
    try:
        vault_path_raw = get_vault_path()
    except ConfigError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        sys.exit(1)

    vault_path = Path(vault_path_raw)
    layout = ensure_v3_layout(vault_path)
    try:
        qmd = ensure_qmd_ready(vault_path)
    except (FileNotFoundError, subprocess.CalledProcessError) as exc:
        reason = "qmd binary not found" if isinstance(exc, FileNotFoundError) else getattr(exc, "stderr", "").strip() or "qmd init failed"
        qmd = {
            "status": "not_ready",
            "reason": reason,
        }
    if qmd.get("status") not in {None, "ready"}:
        print(json.dumps({"layout": layout, "qmd": qmd}, indent=2, ensure_ascii=False), file=sys.stderr)
        sys.exit(1)
    print(json.dumps({"layout": layout, "qmd": qmd}, indent=2, ensure_ascii=False))


def main() -> None:
    parser = argparse.ArgumentParser(
        prog="paper-distill-admin",
        description="Paper Distill v3 admin utilities",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    p_boot = sub.add_parser("bootstrap", help="Initialize vault directory structure")
    p_boot.set_defaults(func=_bootstrap)

    args = parser.parse_args()
    asyncio.run(args.func(args))


if __name__ == "__main__":
    main()
