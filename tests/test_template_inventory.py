from __future__ import annotations

from server.template_render import available_templates


def test_template_inventory_contains_only_active_templates() -> None:
    assert available_templates() == [
        "inbox-paper.md.j2",
        "knowledge-impact-summary.md.j2",
        "query-note.md.j2",
        "wiki-paper.md.j2",
    ]
