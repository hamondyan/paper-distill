from __future__ import annotations

import asyncio
import json

from server.v3_discovery import discover_papers_v3


def test_discover_papers_writes_inbox_stub_and_updates_seen_cache(
    tmp_path, monkeypatch
) -> None:
    async def fake_search(*args, **kwargs):
        return [
            {
                "title": "Attention Is All You Need",
                "paper_id": "arxiv:1706.03762",
                "source_url": "https://arxiv.org/abs/1706.03762",
            }
        ]

    monkeypatch.setattr("server.v3_discovery.search_papers", fake_search)
    monkeypatch.setattr("server.v3_discovery.get_vault_path", lambda: str(tmp_path))

    result = asyncio.run(discover_papers_v3(query="transformer"))

    inbox_files = list((tmp_path / "inbox").glob("*.md"))
    assert len(inbox_files) == 1
    assert "#approved" not in inbox_files[0].read_text(encoding="utf-8")
    cache = json.loads(
        (tmp_path / ".state" / "seen_papers.json").read_text(encoding="utf-8")
    )
    assert cache["arxiv:1706.03762"]["score"] >= 0
    assert result["saved"][0]["paper_id"] == "arxiv:1706.03762"


def test_discover_papers_skips_seen_ids(tmp_path, monkeypatch) -> None:
    (tmp_path / ".state").mkdir(parents=True)
    (tmp_path / ".state" / "seen_papers.json").write_text(
        '{"arxiv:1706.03762": {"score": 88}}\n',
        encoding="utf-8",
    )

    async def fake_search(*args, **kwargs):
        return [
            {
                "title": "Attention Is All You Need",
                "paper_id": "arxiv:1706.03762",
                "source_url": "https://arxiv.org/abs/1706.03762",
            }
        ]

    monkeypatch.setattr("server.v3_discovery.search_papers", fake_search)
    monkeypatch.setattr("server.v3_discovery.get_vault_path", lambda: str(tmp_path))

    result = asyncio.run(discover_papers_v3(query="transformer"))

    assert result["saved"] == []
    assert result["skipped_seen"] == ["arxiv:1706.03762"]
