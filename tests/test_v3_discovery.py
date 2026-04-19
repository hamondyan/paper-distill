from __future__ import annotations

import asyncio

from server.v3_discovery import discover_papers_v3


def test_discover_papers_returns_ranked_chat_results_without_writing_vault(
    tmp_path, monkeypatch
) -> None:
    async def fake_search(*args, **kwargs):
        return [
            {
                "title": "Attention Is All You Need",
                "paper_id": "arxiv:1706.03762",
                "source_url": "https://arxiv.org/abs/1706.03762",
                "abstract": "Transformer paper.",
                "venue": "NeurIPS",
                "year": 2017,
                "authors": ["Ashish Vaswani", "Noam Shazeer"],
            }
        ]

    async def fake_score(*args, **kwargs):
        return [
            {
                "title": "Attention Is All You Need",
                "paper_id": "arxiv:1706.03762",
                "source_url": "https://arxiv.org/abs/1706.03762",
                "abstract": "Transformer paper.",
                "venue": "NeurIPS",
                "year": 2017,
                "authors": ["Ashish Vaswani", "Noam Shazeer"],
                "_score": 0.91,
                "_score_breakdown": {"topic_fit": 0.8},
                "best_topic": "sequence modeling",
            }
        ]

    def fail_layout(*args, **kwargs):
        raise AssertionError("discover_papers_v3 must not initialize vault layout")

    monkeypatch.setattr("server.v3_discovery.query_paper_sources_v3", fake_search)
    monkeypatch.setattr("server.v3_discovery.score_papers_v3", fake_score, raising=False)
    monkeypatch.setattr("server.v3_discovery.ensure_v3_layout", fail_layout, raising=False)

    result = asyncio.run(discover_papers_v3(query="transformer"))

    assert result["count"] == 1
    assert result["results"] == [
        {
            "paper_id": "arxiv:1706.03762",
            "title": "Attention Is All You Need",
            "score": 91,
            "source_url": "https://arxiv.org/abs/1706.03762",
            "arxiv_id": "1706.03762",
            "arxiv_url": "https://arxiv.org/abs/1706.03762",
            "abstract": "Transformer paper.",
            "venue": "NeurIPS",
            "year": 2017,
            "authors": ["Ashish Vaswani", "Noam Shazeer"],
            "best_topic": "sequence modeling",
            "score_breakdown": {"topic_fit": 0.8},
        }
    ]
    assert not (tmp_path / "inbox").exists()
    assert not (tmp_path / ".state" / "seen_papers.json").exists()


def test_discover_papers_scores_results_before_returning(monkeypatch) -> None:
    score_calls = []

    async def fake_search(*args, **kwargs):
        return [
            {
                "title": "Low Raw Score",
                "paper_id": "arxiv:2501.00001",
                "source_url": "https://arxiv.org/abs/2501.00001",
            }
        ]

    async def fake_score(papers):
        score_calls.append(papers)
        return [
            {
                "title": "Low Raw Score",
                "paper_id": "arxiv:2501.00001",
                "source_url": "https://arxiv.org/abs/2501.00001",
                "_score": 0.42,
            }
        ]

    monkeypatch.setattr("server.v3_discovery.query_paper_sources_v3", fake_search)
    monkeypatch.setattr("server.v3_discovery.score_papers_v3", fake_score, raising=False)

    result = asyncio.run(discover_papers_v3(query="robotics"))

    assert len(score_calls) == 1
    assert result["results"][0]["score"] == 42


def test_discover_papers_exposes_ingestable_arxiv_identity(monkeypatch) -> None:
    async def fake_search(*args, **kwargs):
        return [
            {
                "title": "Arxiv Native Candidate",
                "paper_id": "arxiv:2501.00001",
                "arxiv_id": "2501.00001",
            }
        ]

    async def fake_score(papers):
        return [
            {
                "title": "Arxiv Native Candidate",
                "paper_id": "arxiv:2501.00001",
                "arxiv_id": "2501.00001",
                "_score": 0.8,
            }
        ]

    monkeypatch.setattr("server.v3_discovery.query_paper_sources_v3", fake_search)
    monkeypatch.setattr("server.v3_discovery.score_papers_v3", fake_score, raising=False)

    result = asyncio.run(discover_papers_v3(query="robotics"))

    assert result["results"][0]["source_url"] == "https://arxiv.org/abs/2501.00001"
    assert result["results"][0]["arxiv_id"] == "2501.00001"
    assert result["results"][0]["arxiv_url"] == "https://arxiv.org/abs/2501.00001"


def test_discover_papers_is_stateless_between_runs(monkeypatch) -> None:
    async def fake_search(*args, **kwargs):
        return [
            {
                "title": "Repeatable Candidate",
                "paper_id": "arxiv:2501.00002",
                "source_url": "https://arxiv.org/abs/2501.00002",
            }
        ]

    async def fake_score(papers):
        return [dict(papers[0], _score=0.7)]

    monkeypatch.setattr("server.v3_discovery.query_paper_sources_v3", fake_search)
    monkeypatch.setattr("server.v3_discovery.score_papers_v3", fake_score, raising=False)

    first = asyncio.run(discover_papers_v3(query="robotics"))
    second = asyncio.run(discover_papers_v3(query="robotics"))

    assert first["results"] == second["results"]
    assert first["results"][0]["paper_id"] == "arxiv:2501.00002"


def test_discover_papers_skips_items_without_identity_or_title(monkeypatch) -> None:
    async def fake_search(*args, **kwargs):
        return []

    async def fake_score(*args, **kwargs):
        return [
            {"paper_id": "", "title": "Missing ID", "_score": 1.0},
            {"paper_id": None, "title": "None ID", "_score": 1.0},
            {"paper_id": "arxiv:2501.00003", "title": "", "_score": 1.0},
            {"paper_id": "arxiv:2501.00005", "title": None, "_score": 1.0},
            {
                "paper_id": "arxiv:2501.00004",
                "title": "Complete",
                "source_url": "https://arxiv.org/abs/2501.00004",
                "_score": 0.5,
            },
        ]

    monkeypatch.setattr("server.v3_discovery.query_paper_sources_v3", fake_search)
    monkeypatch.setattr("server.v3_discovery.score_papers_v3", fake_score, raising=False)

    result = asyncio.run(discover_papers_v3(query="robotics"))

    assert [item["paper_id"] for item in result["results"]] == ["arxiv:2501.00004"]


def test_discover_papers_clamps_negative_scores_to_zero(monkeypatch) -> None:
    async def fake_search(*args, **kwargs):
        return [
            {
                "title": "Negative Score",
                "paper_id": "arxiv:2501.00006",
                "source_url": "https://arxiv.org/abs/2501.00006",
            }
        ]

    async def fake_score(papers):
        return [dict(papers[0], _score=-0.8)]

    monkeypatch.setattr("server.v3_discovery.query_paper_sources_v3", fake_search)
    monkeypatch.setattr("server.v3_discovery.score_papers_v3", fake_score, raising=False)

    result = asyncio.run(discover_papers_v3(query="robotics"))

    assert result["results"][0]["score"] == 0
