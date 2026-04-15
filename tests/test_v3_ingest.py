from __future__ import annotations

import asyncio
import tempfile
import unittest
from pathlib import Path
from unittest.mock import AsyncMock, patch

import yaml

from server.arxiv_capture_adapter import CleanedArxivDocument
from server.v3_bootstrap import paper_filename


def _read_frontmatter(path: Path) -> dict:
    content = path.read_text(encoding="utf-8")
    _, remainder = content.split("---\n", 1)
    fm_text, _ = remainder.split("\n---\n", 1)
    return yaml.safe_load(fm_text) or {}


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
    def test_approved_inbox_mode_only_ingests_body_marked_notes(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            vault_root = Path(tmpdir)
            inbox_dir = vault_root / "inbox" / "2026-04-15"
            inbox_dir.mkdir(parents=True)

            approved_note = inbox_dir / "approved.md"
            approved_note.write_text(
                """---
paper_id: arxiv:2501.00001
title: Approved Paper
source_url: https://arxiv.org/abs/2501.00001
---

This note is ready for ingest.
#approved
""",
                encoding="utf-8",
            )
            frontmatter_only_note = inbox_dir / "frontmatter-only.md"
            frontmatter_only_note.write_text(
                """---
paper_id: arxiv:2501.00002
title: Not Yet Approved
source_url: https://arxiv.org/abs/2501.00002
body: "#approved"
---

This note is still pending review.
""",
                encoding="utf-8",
            )

            captured = _cleaned_doc("Approved Paper", "# Approved Paper\n\nBody text.")

            with patch("server.v3_ingest.get_vault_path", return_value=tmpdir):
                with patch("server.v3_ingest.ensure_v3_layout", return_value={"created": []}):
                    with patch(
                        "server.v3_ingest.capture_arxiv_source",
                        new=AsyncMock(return_value=captured),
                    ) as capture_mock:
                        from server.v3_ingest import ingest_and_read_v3

                        result = asyncio.run(ingest_and_read_v3("approved"))

            self.assertEqual(capture_mock.await_count, 1)
            self.assertEqual(result["items"][0]["paper_id"], "arxiv:2501.00001")
            raw_path = Path(result["items"][0]["path"])
            self.assertEqual(raw_path.name, paper_filename("Approved Paper", "arxiv:2501.00001"))
            self.assertTrue(raw_path.exists())

            frontmatter = _read_frontmatter(raw_path)
            self.assertEqual(frontmatter["type"], "raw_evidence")
            self.assertEqual(frontmatter["paper_id"], "arxiv:2501.00001")
            self.assertEqual(frontmatter["title"], "Approved Paper")
            self.assertEqual(frontmatter["source_url"], "https://arxiv.org/abs/2501.00001")
            self.assertIn("captured_at", frontmatter)
            self.assertIn("content_hash", frontmatter)
            self.assertNotIn("#approved", raw_path.read_text(encoding="utf-8"))

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

    def test_approved_batch_continues_after_one_capture_failure(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            vault_root = Path(tmpdir)
            inbox_dir = vault_root / "inbox" / "2026-04-15"
            inbox_dir.mkdir(parents=True)

            good_note = inbox_dir / "good.md"
            good_note.write_text(
                """---
paper_id: arxiv:2501.00005
title: Good Paper
source_url: https://arxiv.org/abs/2501.00005
---

This note is approved.
#approved
""",
                encoding="utf-8",
            )
            bad_note = inbox_dir / "bad.md"
            bad_note.write_text(
                """---
paper_id: arxiv:2501.00006
title: Broken Paper
source_url: https://arxiv.org/abs/2501.00006
---

This note is approved, but capture will fail.
#approved
""",
                encoding="utf-8",
            )

            captures = [
                _cleaned_doc("Good Paper", "# Good Paper\n\nWorking body."),
            ]

            async def fake_capture(paper: dict, **_kwargs):
                if paper["paper_id"] == "arxiv:2501.00005":
                    return captures[0]
                raise ValueError("unsupported capture path")

            with patch("server.v3_ingest.get_vault_path", return_value=tmpdir):
                with patch("server.v3_ingest.ensure_v3_layout", return_value={"created": []}):
                    with patch("server.v3_ingest.capture_arxiv_source", new=AsyncMock(side_effect=fake_capture)):
                        from server.v3_ingest import ingest_and_read_v3

                        result = asyncio.run(ingest_and_read_v3("approved"))

            self.assertEqual(len(result["items"]), 1)
            self.assertEqual(result["items"][0]["paper_id"], "arxiv:2501.00005")
            self.assertEqual(len(result["errors"]), 1)
            self.assertEqual(result["errors"][0]["paper_id"], "arxiv:2501.00006")
            self.assertIn("unsupported capture path", result["errors"][0]["error"])

    def test_approved_inbox_note_uses_paper_id_for_ar5iv_source_url(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            vault_root = Path(tmpdir)
            inbox_dir = vault_root / "inbox" / "2026-04-15"
            inbox_dir.mkdir(parents=True)

            note = inbox_dir / "ar5iv.md"
            note.write_text(
                """---
paper_id: arxiv:2501.00007
title: Ar5iv Paper
source_url: https://ar5iv.labs.arxiv.org/html/2501.00007
---

Approved discovery stub.
#approved
""",
                encoding="utf-8",
            )

            captured = _cleaned_doc("Ar5iv Paper", "# Ar5iv Paper\n\nBody text.")

            async def fake_capture(paper: dict, **_kwargs):
                self.assertEqual(paper["paper_id"], "arxiv:2501.00007")
                self.assertEqual(paper["arxiv_id"], "2501.00007")
                return captured

            with patch("server.v3_ingest.get_vault_path", return_value=tmpdir):
                with patch("server.v3_ingest.ensure_v3_layout", return_value={"created": []}):
                    with patch("server.v3_ingest.capture_arxiv_source", new=AsyncMock(side_effect=fake_capture)):
                        from server.v3_ingest import ingest_and_read_v3

                        result = asyncio.run(ingest_and_read_v3("approved"))

            self.assertEqual(len(result["items"]), 1)
            self.assertEqual(result["items"][0]["paper_id"], "arxiv:2501.00007")
            self.assertEqual(result["errors"], [])

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

    def test_frontmatter_only_approval_marker_does_not_count(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            vault_root = Path(tmpdir)
            inbox_dir = vault_root / "inbox" / "2026-04-15"
            inbox_dir.mkdir(parents=True)
            note = inbox_dir / "pending.md"
            note.write_text(
                """---
paper_id: arxiv:2501.00004
title: Pending Paper
body: "#approved"
---

This body is not approved.
""",
                encoding="utf-8",
            )

            with patch("server.v3_ingest.get_vault_path", return_value=tmpdir):
                with patch("server.v3_ingest.ensure_v3_layout", return_value={"created": []}):
                    with patch("server.v3_ingest.capture_arxiv_source", new=AsyncMock()) as capture_mock:
                        from server.v3_ingest import ingest_and_read_v3

                        result = asyncio.run(ingest_and_read_v3("approved"))

            self.assertEqual(result["items"], [])
            self.assertEqual(capture_mock.await_count, 0)


if __name__ == "__main__":
    unittest.main()
