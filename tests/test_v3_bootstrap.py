from server.v3_bootstrap import ensure_v3_layout, paper_filename


def test_ensure_v3_layout_creates_empty_vault_tree(tmp_path):
    result = ensure_v3_layout(tmp_path)

    assert (tmp_path / "inbox").is_dir()
    assert (tmp_path / "raw" / "evidence").is_dir()
    assert (tmp_path / "wiki" / "papers").is_dir()
    assert (tmp_path / "wiki" / "concepts").is_dir()
    assert (tmp_path / "insights" / "ideas").is_dir()
    assert (tmp_path / "insights" / "conversations").is_dir()
    assert (tmp_path / "exports" / "presentations").is_dir()
    assert (tmp_path / ".state" / "seen_papers.json").read_text(encoding="utf-8") == "{}\n"
    assert (tmp_path / "vault-log.md").exists()
    assert paper_filename("Attention Is All You Need", "arxiv:1706.03762") == "attention-is-all-you-need--arxiv-1706.03762.md"
    assert paper_filename("A Study", "doi:10.1145/123/456") == "a-study--doi-10.1145-123-456.md"
    assert result["created"]
