from __future__ import annotations

import asyncio
import json

import yaml

from server.v3_discovery import discover_papers_v3


def test_discover_papers_writes_inbox_stub_and_updates_seen_cache(
    tmp_path, monkeypatch
) -> None:
    async def fake_search(*args, **kwargs):
        return [
            {
                "title": "Attention: Is All You Need",
                "paper_id": "arxiv:1706.03762",
                "source_url": "https://arxiv.org/abs/1706.03762",
            }
        ]

    monkeypatch.setattr("server.v3_discovery.search_papers", fake_search)
    monkeypatch.setattr("server.v3_discovery.get_vault_path", lambda: str(tmp_path))

    result = asyncio.run(discover_papers_v3(query="transformer"))

    inbox_files = list((tmp_path / "inbox").glob("*.md"))
    assert len(inbox_files) == 1
    stub_text = inbox_files[0].read_text(encoding="utf-8")
    _, remainder = stub_text.split("---\n", 1)
    frontmatter_text, _body = remainder.split("\n---\n", 1)
    frontmatter = yaml.safe_load(frontmatter_text)

    assert 'title: "Attention: Is All You Need"' in stub_text
    assert 'source_url: "https://arxiv.org/abs/1706.03762"' in stub_text
    assert frontmatter["title"] == "Attention: Is All You Need"
    assert frontmatter["source_url"] == "https://arxiv.org/abs/1706.03762"
    assert "#approved" not in stub_text
    cache = json.loads(
        (tmp_path / ".state" / "seen_papers.json").read_text(encoding="utf-8")
    )
    assert cache["arxiv:1706.03762"]["score"] >= 0
    assert result["saved"][0]["paper_id"] == "arxiv:1706.03762"


def test_discover_papers_scores_results_before_saving(
    tmp_path, monkeypatch
) -> None:
    async def fake_search(*args, **kwargs):
        return [
            {
                "title": "Attention: Is All You Need",
                "paper_id": "arxiv:1706.03762",
                "source_url": "https://arxiv.org/abs/1706.03762",
                "score": 12,
            }
        ]

    score_calls = []

    async def fake_score(*args, **kwargs):
        score_calls.append((args, kwargs))
        return [
            {
                "title": "Attention: Is All You Need",
                "paper_id": "arxiv:1706.03762",
                "source_url": "https://arxiv.org/abs/1706.03762",
                "_score": 91,
            }
        ]

    monkeypatch.setattr("server.v3_discovery.search_papers", fake_search)
    monkeypatch.setattr("server.v3_discovery.score_papers", fake_score, raising=False)
    monkeypatch.setattr("server.v3_discovery.get_vault_path", lambda: str(tmp_path))

    asyncio.run(discover_papers_v3(query="transformer"))

    cache = json.loads(
        (tmp_path / ".state" / "seen_papers.json").read_text(encoding="utf-8")
    )
    assert cache["arxiv:1706.03762"]["score"] == 91
    assert len(score_calls) == 1


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
