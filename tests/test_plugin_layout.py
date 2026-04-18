from pathlib import Path


def test_mcp_launcher_uses_shared_root_helper() -> None:
    launcher = Path("scripts/run-mcp.sh").read_text(encoding="utf-8")
    assert "plugin-root.sh" in launcher
