from __future__ import annotations

import asyncio
import tempfile
import unittest
from pathlib import Path
from unittest.mock import AsyncMock, patch

from server.arxiv_capture_adapter import CleanedArxivDocument
from server.v3_bootstrap import paper_filename
from tests.helpers import read_frontmatter as _read_frontmatter


def _cleaned_doc(title: str, markdown: str, capture_source: str = "arxiv_native_html") -> CleanedArxivDocument:
    return CleanedArxivDocument(
        title=title,
        abstract="Abstract",
        markdown=markdown,
        sections=[],
        appendix_snapshot=[],
        quality={"body_chars": len(markdown)},
        figures=[],
        tables=[],
        equations=[],
        capture_source=capture_source,
        capture_method="arxiv_native_html_cleaned",
    )


class V3IngestTest(unittest.TestCase):
    def test_split_direct_input_items_handles_agent_batch_formats(self) -> None:
        from server.v3_ingest import _split_direct_input_items

        raw = """
        - https://arxiv.org/abs/2405.12213
        2. 1706.03762
        3) 10.48550/arxiv.2410.24164; https://arxiv.org/pdf/2501.00001.pdf, https://arxiv.org/abs/2501.00002
        """

        self.assertEqual(
            _split_direct_input_items(raw),
            [
                "https://arxiv.org/abs/2405.12213",
                "1706.03762",
                "10.48550/arxiv.2410.24164",
                "https://arxiv.org/pdf/2501.00001.pdf",
                "https://arxiv.org/abs/2501.00002",
            ],
        )

    def test_split_direct_input_items_keeps_single_url_intact(self) -> None:
        from server.v3_ingest import _split_direct_input_items

        self.assertEqual(
            _split_direct_input_items("https://arxiv.org/abs/2405.12213"),
            ["https://arxiv.org/abs/2405.12213"],
        )

    def test_direct_input_accepts_bare_arxiv_id(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            captured = _cleaned_doc("Bare ID Paper", "# Bare ID Paper\n\nBody.")

            with patch("server.v3_ingest.get_vault_path", return_value=tmpdir):
                with patch("server.v3_ingest.ensure_v3_layout", return_value={"created": []}):
                    with patch(
                        "server.v3_ingest.fetch_arxiv_record",
                        new=AsyncMock(
                            return_value={
                                "paper_id": "arxiv:1706.03762",
                                "title": "Bare ID Paper",
                                "arxiv_id": "1706.03762",
                                "authors": ["Ashish Vaswani"],
                                "year": 2017,
                            }
                        ),
                    ) as fetch_mock:
                        with patch("server.v3_ingest.capture_arxiv_source", new=AsyncMock(return_value=captured)):
                            from server.v3_ingest import ingest_and_read_v3

                            result = asyncio.run(ingest_and_read_v3("1706.03762"))

        self.assertEqual(fetch_mock.await_count, 1)
        self.assertEqual(result["captured_count"], 1)
        self.assertEqual(result["error_count"], 0)
        self.assertEqual(result["items"][0]["input"], "1706.03762")
        self.assertEqual(result["items"][0]["paper_id"], "arxiv:1706.03762")

    def test_direct_input_accepts_arxiv_doi(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            captured = _cleaned_doc("DOI Paper", "# DOI Paper\n\nBody.")

            with patch("server.v3_ingest.get_vault_path", return_value=tmpdir):
                with patch("server.v3_ingest.ensure_v3_layout", return_value={"created": []}):
                    with patch(
                        "server.v3_ingest.fetch_arxiv_record",
                        new=AsyncMock(
                            return_value={
                                "paper_id": "arxiv:2405.12213",
                                "title": "DOI Paper",
                                "arxiv_id": "2405.12213",
                                "authors": ["Ada Lovelace"],
                                "year": 2024,
                            }
                        ),
                    ) as fetch_mock:
                        with patch("server.v3_ingest.capture_arxiv_source", new=AsyncMock(return_value=captured)):
                            from server.v3_ingest import ingest_and_read_v3

                            result = asyncio.run(ingest_and_read_v3("10.48550/arxiv.2405.12213"))

        self.assertEqual(fetch_mock.await_count, 1)
        self.assertEqual(result["captured_count"], 1)
        self.assertEqual(result["error_count"], 0)
        self.assertEqual(result["items"][0]["input"], "10.48550/arxiv.2405.12213")
        self.assertEqual(result["items"][0]["paper_id"], "arxiv:2405.12213")

    def test_direct_input_ingests_multiple_resolved_arxiv_items(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            docs = {
                "2405.12213": _cleaned_doc("First Paper", "# First Paper\n\nBody."),
                "1706.03762": _cleaned_doc("Second Paper", "# Second Paper\n\nBody."),
            }

            async def fake_fetch(arxiv_id: str):
                return {
                    "paper_id": f"arxiv:{arxiv_id}",
                    "title": "First Paper" if arxiv_id == "2405.12213" else "Second Paper",
                    "arxiv_id": arxiv_id,
                    "authors": ["Ada Lovelace"],
                    "year": 2025,
                }

            async def fake_capture(paper: dict, **_kwargs):
                return docs[paper["arxiv_id"]]

            raw_input = """
            - https://arxiv.org/abs/2405.12213
            - 1706.03762
            """

            with patch("server.v3_ingest.get_vault_path", return_value=tmpdir):
                with patch("server.v3_ingest.ensure_v3_layout", return_value={"created": []}):
                    with patch("server.v3_ingest.fetch_arxiv_record", new=AsyncMock(side_effect=fake_fetch)):
                        with patch("server.v3_ingest.capture_arxiv_source", new=AsyncMock(side_effect=fake_capture)):
                            from server.v3_ingest import ingest_and_read_v3

                            result = asyncio.run(ingest_and_read_v3(raw_input))

        self.assertEqual(result["captured_count"], 2)
        self.assertEqual(result["error_count"], 0)
        self.assertEqual([item["paper_id"] for item in result["items"]], ["arxiv:2405.12213", "arxiv:1706.03762"])
        self.assertEqual(result["errors"], [])

    def test_direct_input_reports_invalid_items_without_stopping_batch(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            captured = _cleaned_doc("Good Paper", "# Good Paper\n\nBody.")

            with patch("server.v3_ingest.get_vault_path", return_value=tmpdir):
                with patch("server.v3_ingest.ensure_v3_layout", return_value={"created": []}):
                    with patch(
                        "server.v3_ingest.fetch_arxiv_record",
                        new=AsyncMock(
                            return_value={
                                "paper_id": "arxiv:2405.12213",
                                "title": "Good Paper",
                                "arxiv_id": "2405.12213",
                                "authors": ["Ada Lovelace"],
                                "year": 2024,
                            }
                        ),
                    ):
                        with patch("server.v3_ingest.capture_arxiv_source", new=AsyncMock(return_value=captured)):
                            from server.v3_ingest import ingest_and_read_v3

                            result = asyncio.run(
                                ingest_and_read_v3("openvla, https://arxiv.org/abs/2405.12213")
                            )

        self.assertEqual(result["captured_count"], 1)
        self.assertEqual(result["error_count"], 1)
        self.assertEqual(result["items"][0]["paper_id"], "arxiv:2405.12213")
        self.assertEqual(
            result["resolved_inputs"],
            [
                {
                    "input": "https://arxiv.org/abs/2405.12213",
                    "arxiv_id": "2405.12213",
                    "source_url": "https://arxiv.org/abs/2405.12213",
                }
            ],
        )
        self.assertEqual(result["unresolved_inputs"], ["openvla"])
        self.assertEqual(result["errors"][0]["input"], "openvla")
        self.assertIn("resolved to an arXiv", result["errors"][0]["error"])
        self.assertNotIn("error", result)

    def test_direct_input_skips_duplicate_arxiv_ids_in_same_batch(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            captured = _cleaned_doc("Duplicate Paper", "# Duplicate Paper\n\nBody.")

            with patch("server.v3_ingest.get_vault_path", return_value=tmpdir):
                with patch("server.v3_ingest.ensure_v3_layout", return_value={"created": []}):
                    with patch(
                        "server.v3_ingest.fetch_arxiv_record",
                        new=AsyncMock(
                            return_value={
                                "paper_id": "arxiv:2405.12213",
                                "title": "Duplicate Paper",
                                "arxiv_id": "2405.12213",
                                "authors": ["Ada Lovelace"],
                                "year": 2024,
                            }
                        ),
                    ) as fetch_mock:
                        with patch(
                            "server.v3_ingest.capture_arxiv_source",
                            new=AsyncMock(return_value=captured),
                        ) as capture_mock:
                            from server.v3_ingest import ingest_and_read_v3

                            result = asyncio.run(
                                ingest_and_read_v3(
                                    "https://arxiv.org/abs/2405.12213, 2405.12213, https://arxiv.org/pdf/2405.12213.pdf"
                                )
                            )

        self.assertEqual(fetch_mock.await_count, 1)
        self.assertEqual(capture_mock.await_count, 1)
        self.assertEqual(result["captured_count"], 1)
        self.assertEqual(result["error_count"], 0)
        self.assertEqual(result["skipped_duplicates"], ["2405.12213", "2405.12213"])

    def test_direct_url_reingest_with_title_change_overwrites_same_raw_path(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            vault_root = Path(tmpdir)
            vault_root.mkdir(parents=True, exist_ok=True)

            first_doc = _cleaned_doc("Direct Paper", "# First capture")
            second_doc = _cleaned_doc("Renamed Paper", "# Second capture")
            url = "https://arxiv.org/abs/2501.00003"

            capture_count = 0

            async def fake_capture(paper: dict, **_kwargs):
                nonlocal capture_count
                capture_count += 1
                if capture_count == 1:
                    return first_doc
                return second_doc

            with patch("server.v3_ingest.get_vault_path", return_value=tmpdir):
                with patch("server.v3_ingest.ensure_v3_layout", return_value={"created": []}):
                    with patch(
                        "server.v3_ingest.fetch_arxiv_record",
                        new=AsyncMock(
                            return_value={
                                "paper_id": "arxiv:2501.00003",
                                "title": "Direct Paper",
                                "arxiv_id": "2501.00003",
                                "authors": ["Ada Lovelace"],
                                "year": 2025,
                            }
                        ),
                    ):
                        with patch("server.v3_ingest.capture_arxiv_source", new=AsyncMock(side_effect=fake_capture)):
                            from server.v3_ingest import ingest_and_read_v3

                            first = asyncio.run(ingest_and_read_v3(url))
                            second = asyncio.run(ingest_and_read_v3(url))

            first_path = Path(first["items"][0]["path"])
            second_path = Path(second["items"][0]["path"])
            self.assertEqual(first_path, second_path)
            self.assertEqual(first_path.name, paper_filename("Direct Paper", "arxiv:2501.00003"))
            self.assertEqual(first_path.read_text(encoding="utf-8").count("Second capture"), 1)

    def test_approved_input_is_retired_and_does_not_scan_inbox(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            vault_root = Path(tmpdir)
            inbox_dir = vault_root / "inbox"
            inbox_dir.mkdir(parents=True)

            inbox_dir.joinpath("approved.md").write_text(
                """---
paper_id: arxiv:2501.00001
title: Approved Paper
source_url: https://arxiv.org/abs/2501.00001
---

#approved
""",
                encoding="utf-8",
            )

            with patch("server.v3_ingest.get_vault_path", return_value=tmpdir):
                with patch("server.v3_ingest.ensure_v3_layout", return_value={"created": []}):
                    with patch(
                        "server.v3_ingest._read_markdown_note",
                        side_effect=AssertionError("must not scan retired inbox"),
                    ):
                        with patch("server.v3_ingest.capture_arxiv_source", new=AsyncMock()) as capture_mock:
                            from server.v3_ingest import ingest_and_read_v3

                            result = asyncio.run(ingest_and_read_v3("approved"))

            self.assertFalse(result["ok"])
            self.assertEqual(result["items"], [])
            self.assertEqual(result["errors"], [])
            self.assertEqual(result["captured_count"], 0)
            self.assertEqual(result["error_count"], 0)
            self.assertEqual(result["skipped_duplicates"], [])
            self.assertEqual(result["resolved_inputs"], [])
            self.assertEqual(result["unresolved_inputs"], [])
            self.assertIn("retired", result["error"])
            self.assertIn("arXiv", result["error"])
            self.assertEqual(capture_mock.await_count, 0)

    def test_direct_input_rejects_non_arxiv_url(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            with patch("server.v3_ingest.get_vault_path", return_value=tmpdir):
                with patch("server.v3_ingest.ensure_v3_layout", return_value={"created": []}):
                    from server.v3_ingest import ingest_and_read_v3

                    result = asyncio.run(ingest_and_read_v3("https://example.com/paper"))

        self.assertIn("error", result)
        self.assertIn("arXiv", result["error"])

    def test_direct_input_returns_structured_error_when_capture_fails(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            with patch("server.v3_ingest.get_vault_path", return_value=tmpdir):
                with patch("server.v3_ingest.ensure_v3_layout", return_value={"created": []}):
                    with patch(
                        "server.v3_ingest.fetch_arxiv_record",
                        new=AsyncMock(
                            return_value={
                                "paper_id": "arxiv:2501.00008",
                                "title": "Broken Direct Paper",
                                "arxiv_id": "2501.00008",
                                "authors": ["Ada Lovelace"],
                                "year": 2025,
                            }
                        ),
                    ):
                        with patch(
                            "server.v3_ingest.capture_arxiv_source",
                            new=AsyncMock(side_effect=ValueError("capture exploded")),
                        ):
                            from server.v3_ingest import ingest_and_read_v3

                            result = asyncio.run(ingest_and_read_v3("https://arxiv.org/abs/2501.00008"))

        self.assertIn("error", result)
        self.assertIn("capture exploded", result["error"])
        self.assertEqual(result["paper_id"], "arxiv:2501.00008")


if __name__ == "__main__":
    unittest.main()
