from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from server.obsidian_query import query_library_sync
from server.vault_ops import write_markdown


class _CompletedProcess:
    def __init__(self, stdout: str):
        self.stdout = stdout


class ObsidianQueryAdapterTest(unittest.TestCase):
    def test_query_library_falls_back_to_filesystem_scan_with_metadata(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            inbox_dir = Path(tmpdir) / "Paper Distill" / "inbox" / "2026-04-10"
            inbox_dir.mkdir(parents=True, exist_ok=True)
            write_markdown(
                inbox_dir / "paper.md",
                {
                    "paper_id": "doi:test",
                    "status": "approved",
                    "title": "Fallback Query Paper",
                },
                "# Example",
            )

            with patch(
                "server.obsidian_query.available_obsidian_query_providers",
                return_value=[],
            ):
                result = query_library_sync(tmpdir, section="inbox")

        self.assertEqual(result["provider"], "filesystem_scan")
        self.assertTrue(result["fallback_used"])
        self.assertEqual(result["stats"]["inbox"], 1)
        self.assertIn("list", result["capabilities"])
        self.assertIn("keyword_search", result["capabilities"])

    def test_query_library_prefers_official_cli_when_available(self) -> None:
        provider = {
            "name": "official_cli",
            "label": "Obsidian CLI",
            "capabilities": ["list", "property_filters", "tag_filters", "keyword_search"],
        }
        expected = {
            "stats": {"papers": 1},
            "sections": {"papers": [{"paper_id": "doi:test", "title": "CLI Paper"}]},
        }

        with tempfile.TemporaryDirectory() as tmpdir:
            with patch(
                "server.obsidian_query.available_obsidian_query_providers",
                return_value=[provider],
            ):
                with patch(
                    "server.obsidian_query._query_with_provider",
                    return_value=expected,
                ) as provider_query:
                    result = query_library_sync(tmpdir, section="papers")

        provider_query.assert_called_once()
        self.assertEqual(result["provider"], "official_cli")
        self.assertFalse(result["fallback_used"])
        self.assertEqual(result["stats"]["papers"], 1)
        self.assertEqual(result["sections"]["papers"][0]["title"], "CLI Paper")

    def test_query_library_normalizes_native_official_cli_results(self) -> None:
        def fake_run(args, **_kwargs):
            command = args[1]
            if command == "files":
                return _CompletedProcess(
                    "\n".join(
                        [
                            "Paper Distill/inbox/2026-04-10/matching.md",
                            "Paper Distill/inbox/2026-04-10/other.md",
                            "Paper Distill/inbox/_index.md",
                            "Paper Distill/inbox/inbox.base",
                        ]
                    )
                )
            if command == "properties" and "path=Paper Distill/inbox/2026-04-10/matching.md" in args:
                return _CompletedProcess(
                    """
                    {
                      "paper_id": "doi:match",
                      "status": "approved",
                      "title": "Matching CLI Paper",
                      "abstract": "This abstract should become a compact preview for the normalized item.",
                      "matched_topics": ["robotics"],
                      "retrieved_at": "2026-04-10T10:00:00"
                    }
                    """
                )
            if command == "properties" and "path=Paper Distill/inbox/2026-04-10/other.md" in args:
                return _CompletedProcess(
                    """
                    {
                      "paper_id": "doi:other",
                      "status": "proposed",
                      "title": "Other CLI Paper",
                      "matched_topics": ["robotics"],
                      "retrieved_at": "2026-04-09T10:00:00"
                    }
                    """
                )
            raise AssertionError(f"unexpected command: {args}")

        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            inbox_dir = root / "Paper Distill" / "inbox" / "2026-04-10"
            inbox_dir.mkdir(parents=True, exist_ok=True)
            (inbox_dir / "matching.md").touch()
            (inbox_dir / "other.md").touch()

            with patch("server.obsidian_query.shutil.which", return_value="/usr/local/bin/obsidian"):
                with patch("server.obsidian_query.get_paper_distill_settings", return_value={"obsidian_query": {}}):
                    with patch("server.obsidian_query._is_open_obsidian_vault", return_value=True, create=True):
                        with patch("server.obsidian_query.subprocess.run", side_effect=fake_run):
                            result = query_library_sync(
                                tmpdir,
                                section="inbox",
                                status="approved",
                                topic="robotics",
                                sort_by="retrieved_at",
                            )

        self.assertEqual(result["provider"], "official_cli")
        self.assertFalse(result["fallback_used"])
        self.assertEqual(result["stats"]["inbox"], 1)
        item = result["sections"]["inbox"][0]
        self.assertEqual(item["paper_id"], "doi:match")
        self.assertEqual(item["title"], "Matching CLI Paper")
        self.assertEqual(item["_path"], "Paper Distill/inbox/2026-04-10/matching.md")
        self.assertIn("This abstract should become", item["preview_text"])
        self.assertNotIn("abstract", item)

    def test_query_library_falls_back_when_native_official_cli_fails(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            inbox_dir = Path(tmpdir) / "Paper Distill" / "inbox" / "2026-04-10"
            inbox_dir.mkdir(parents=True, exist_ok=True)
            write_markdown(
                inbox_dir / "fallback.md",
                {
                    "paper_id": "doi:fallback",
                    "status": "approved",
                    "title": "Fallback Paper",
                },
                "# Fallback",
            )

            with patch("server.obsidian_query.shutil.which", return_value="/usr/local/bin/obsidian"):
                with patch("server.obsidian_query.get_paper_distill_settings", return_value={"obsidian_query": {}}):
                    with patch("server.obsidian_query._is_open_obsidian_vault", return_value=True, create=True):
                        with patch("server.obsidian_query.subprocess.run", side_effect=RuntimeError("cli down")):
                            result = query_library_sync(tmpdir, section="inbox")

        self.assertEqual(result["provider"], "filesystem_scan")
        self.assertTrue(result["fallback_used"])
        self.assertEqual(result["available_providers"], ["official_cli"])
        self.assertEqual(result["stats"]["inbox"], 1)
        self.assertEqual(result["sections"]["inbox"][0]["title"], "Fallback Paper")

    def test_query_library_falls_back_when_vault_is_not_open_in_obsidian(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            paper_dir = Path(tmpdir) / "Paper Distill" / "wiki" / "papers"
            paper_dir.mkdir(parents=True, exist_ok=True)
            write_markdown(
                paper_dir / "local-paper.md",
                {
                    "citekey": "local-paper",
                    "title": "Local Paper",
                },
                "# Local Paper",
            )

            with patch("server.obsidian_query.shutil.which", return_value="/usr/local/bin/obsidian"):
                with patch("server.obsidian_query.get_paper_distill_settings", return_value={"obsidian_query": {}}):
                    with patch("server.obsidian_query._is_open_obsidian_vault", return_value=False, create=True):
                        with patch("server.obsidian_query.subprocess.run", return_value=_CompletedProcess("")):
                            result = query_library_sync(tmpdir, section="papers", detail="full")

        self.assertEqual(result["provider"], "filesystem_scan")
        self.assertTrue(result["fallback_used"])
        self.assertEqual(result["stats"]["papers"], 1)
        self.assertEqual(result["sections"]["papers"][0]["title"], "Local Paper")
