from __future__ import annotations

import subprocess
import tempfile
from pathlib import Path


def test_bootstrap_script_uses_current_vault_contract() -> None:
    with tempfile.TemporaryDirectory() as tmpdir:
        repo_root = Path(__file__).resolve().parents[1]
        subprocess.run(
            ["bash", str(repo_root / "scripts" / "bootstrap.sh"), tmpdir],
            check=True,
            cwd=repo_root,
            text=True,
            capture_output=True,
        )

        root = Path(tmpdir) / "Paper Distill"
        for rel_path in (
            "inbox",
            "sources/evidence",
            "wiki/papers",
            "insights/queries",
            "insights/digests",
            "insights/ideas",
            "memory",
            ".state/ir",
        ):
            assert (root / rel_path).exists()

        index_text = (root / "index.md").read_text(encoding="utf-8")
        assert "human landing page" in index_text
        assert "Knowledge map" not in index_text
