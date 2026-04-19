from __future__ import annotations

import subprocess
import tempfile
from pathlib import Path


def test_bootstrap_script_uses_direct_v3_layout() -> None:
    with tempfile.TemporaryDirectory() as tmpdir:
        repo_root = Path(__file__).resolve().parents[1]
        subprocess.run(
            ["bash", str(repo_root / "scripts" / "bootstrap.sh"), tmpdir],
            check=True,
            cwd=repo_root,
            text=True,
            capture_output=True,
        )

        root = Path(tmpdir)
        for rel_path in (
            "raw/evidence",
            "wiki/papers",
            "wiki/concepts",
            "insights/ideas",
            "insights/conversations",
            "exports/presentations",
            ".state",
            "vault-log.md",
        ):
            assert (root / rel_path).exists()

        assert not (root / "inbox").exists()
        assert not (root / ".state" / "seen_papers.json").exists()
        assert not (root / "Paper Distill").exists()
        assert not (root / "index.md").exists()
