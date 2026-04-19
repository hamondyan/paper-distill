from __future__ import annotations

import asyncio
from pathlib import Path

from server import tools_distill
from server.v3_distill import distill_paper_v3, distill_papers_v3
from tests.helpers import read_frontmatter as _read_frontmatter


def _write_raw_evidence(
    vault_path: Path,
    filename: str = "attention.md",
    *,
    paper_id: str = "arxiv:1706.03762",
    title: str = "Attention Is All You Need",
) -> Path:
    evidence_dir = vault_path / "raw" / "evidence"
    evidence_dir.mkdir(parents=True, exist_ok=True)
    path = evidence_dir / filename
    path.write_text(
        "---\n"
        "type: raw_evidence\n"
        f"paper_id: {paper_id}\n"
        f"title: {title}\n"
        "source_url: https://arxiv.org/abs/1706.03762\n"
        "---\n\n"
        f"# {title}\n\n"
        "Raw captured source material.\n",
        encoding="utf-8",
    )
    return path


def test_distill_paper_returns_payload_request_without_writing(tmp_path: Path) -> None:
    evidence_path = _write_raw_evidence(tmp_path)

    result = distill_paper_v3(tmp_path, "1706.03762")

    assert result["ok"] is False
    assert result["status"] == "needs_distillation_payload"
    assert result["paper_id"] == "arxiv:1706.03762"
    assert result["raw_evidence_path"] == str(evidence_path)
    assert "distilled.frontmatter" in result["message"]
    assert not (tmp_path / "wiki" / "papers").exists()


def test_distill_paper_writes_canonical_page_from_payload(tmp_path: Path) -> None:
    _write_raw_evidence(tmp_path)

    result = distill_paper_v3(
        tmp_path,
        "arxiv:1706.03762",
        distilled={
            "target": "attention-is-all-you-need--arxiv-1706.03762",
            "frontmatter": {
                "paper_id": "arxiv:1706.03762",
                "title": "Attention Is All You Need",
                "year": 2017,
                "venue": "NeurIPS",
                "source_layer": "wiki",
                "key_concepts_topk": ["Transformer"],
            },
            "body": "# Attention Is All You Need\n\nIntroduced the [[Transformer]] architecture.",
        },
    )

    path = tmp_path / "wiki" / "papers" / "attention-is-all-you-need--arxiv-1706.03762.md"
    assert result["ok"] is True
    assert result["path"] == str(path)
    assert result["raw_evidence_path"].endswith("attention.md")
    assert result["follow_up"] == [
        "Run qmd update after all writes in this round finish.",
        "Run qmd embed -f after all writes finish if semantic retrieval must reflect the new state immediately.",
    ]
    assert _read_frontmatter(path)["type"] == "paper"


def test_distill_paper_reports_unresolved_input(tmp_path: Path) -> None:
    _write_raw_evidence(tmp_path)

    result = distill_paper_v3(tmp_path, "missing paper")

    assert result == {
        "ok": False,
        "error": "raw evidence not found for input: missing paper",
        "candidates": [],
    }


def test_distill_papers_processes_batch_sequentially(tmp_path: Path) -> None:
    _write_raw_evidence(tmp_path)
    _write_raw_evidence(
        tmp_path,
        "other.md",
        paper_id="arxiv:9999.00000",
        title="Other Paper",
    )

    result = distill_papers_v3(
        tmp_path,
        [
            {
                "input_value": "1706.03762",
                "distilled": {
                    "frontmatter": {
                        "paper_id": "arxiv:1706.03762",
                        "title": "Attention Is All You Need",
                        "year": 2017,
                        "venue": "NeurIPS",
                        "source_layer": "wiki",
                        "key_concepts_topk": ["Transformer"],
                    },
                    "body": "# Attention\n\n[[Transformer]] made attention-only sequence modeling practical.",
                },
            },
            {"input_value": "missing paper"},
        ],
    )

    assert result["ok"] is False
    assert len(result["results"]) == 2
    assert result["results"][0]["ok"] is True
    assert result["results"][1]["ok"] is False
    assert result["results"][1]["error"] == "raw evidence not found for input: missing paper"


def test_distill_paper_tool_offloads_work(monkeypatch) -> None:
    calls: list[str] = []

    async def fake_to_thread(fn, *args, **kwargs):
        calls.append(f"{fn.__name__}:{args[1]}")
        return fn(*args, **kwargs)

    def fake_distill_paper_v3(*_args):
        return {"ok": True}
    fake_distill_paper_v3.__name__ = "distill_paper_v3"

    monkeypatch.setattr(tools_distill.asyncio, "to_thread", fake_to_thread)
    monkeypatch.setattr(tools_distill, "get_vault_path", lambda: "/tmp/vault")
    monkeypatch.setattr(tools_distill, "distill_paper_v3", fake_distill_paper_v3)

    result = asyncio.run(tools_distill.distill_paper("1706.03762", {"body": "[[Transformer]]"}))

    assert result == {"ok": True}
    assert calls == ["distill_paper_v3:1706.03762"]
