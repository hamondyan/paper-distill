from __future__ import annotations

import unittest

from server.search.merger import dedup_merge


class MergerTest(unittest.TestCase):
    def test_formal_venue_overrides_arxiv_placeholder(self) -> None:
        merged = dedup_merge(
            [
                {
                    "title": "Vision Language Action Policies",
                    "authors": ["Jane Doe"],
                    "year": 2025,
                    "doi": "10.1000/example",
                    "source": "arxiv",
                    "venue": "",
                    "arxiv_id": "2501.00001",
                },
                {
                    "title": "Vision Language Action Policies",
                    "authors": ["Jane Doe"],
                    "year": 2025,
                    "doi": "10.1000/example",
                    "source": "dblp",
                    "venue": "IROS",
                },
            ]
        )

        self.assertEqual(len(merged), 1)
        self.assertEqual(merged[0]["venue"], "IROS")

