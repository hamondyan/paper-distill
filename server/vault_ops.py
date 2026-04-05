"""Helpers for initializing and writing Paper Distill vault notes."""
from __future__ import annotations

import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Any

import yaml

from server.paper_utils import first_author_surname, normalise_title
from server.template_render import render_template

LOG = logging.getLogger(__name__)

PAPER_DISTILL_ROOT = "Paper Distill"

_SECTION_DIRS = {
    "inbox": "inbox",
    "raw": "raw",
    "raw_source": "raw/source",
    "raw_notes": "raw/notes",
    "zotero": "zotero",
    "zotero_imports": "zotero/imports",
    "wiki": "wiki",
    "papers": "wiki/papers",
    "concepts": "wiki/concepts",
    "methods": "wiki/methods",
    "topics": "wiki/topics",
    "daily-log": "daily-log",
    "queries": "queries",
}

_INDEX_CONTENT = {
    "master": """---
type: index
section: master
updated: ""
---

# Paper Distill

Research knowledge system with human approval, arXiv-backed source capture, Zotero grounding, and AI-maintained wiki layers.

## Sections

- `inbox/` candidate papers awaiting review
- `raw/source/` cleaned arXiv source captures
- `raw/notes/` CRGP-DNL structured reading notes
- `wiki/` compiled knowledge pages
- `queries/` saved answers and idea analyses
""",
    "inbox": """---
type: index
section: inbox
updated: ""
---

# Inbox

Candidate papers discovered by AI. Review the `status` field in each note:

- `proposed`
- `approved`
- `rejected`
- `deferred`
""",
    "raw": """---
type: index
section: raw
updated: ""
---

# Raw Layer

Dual-layer source capture for approved papers.

- `source/` holds cleaned arXiv captures
- `notes/` holds CRGP-DNL reading notes
""",
    "raw_source": """---
type: index
section: raw/source
updated: ""
---

# Raw Source

Cleaned arXiv full-text captures. This is the stable evidence layer.
""",
    "raw_notes": """---
type: index
section: raw/notes
updated: ""
---

# Raw Notes

CRGP-DNL structured reading notes generated from `raw/source`.
""",
    "zotero": """---
type: index
section: zotero
updated: ""
---

# Zotero Handoff

Local-first Zotero export queue and related handoff files.
""",
    "zotero_imports": """---
type: index
section: zotero/imports
updated: ""
---

# Zotero Imports

Import packs generated for local-first Zotero workflows.
""",
    "wiki": """---
type: index
section: wiki
updated: ""
---

# Wiki

Compiled knowledge derived only from approved raw notes.
""",
    "papers": """---
type: index
section: wiki/papers
updated: ""
---

# Compiled Papers
""",
    "concepts": """---
type: index
section: wiki/concepts
updated: ""
---

# Concepts
""",
    "methods": """---
type: index
section: wiki/methods
updated: ""
---

# Methods
""",
    "topics": """---
type: index
section: wiki/topics
updated: ""
---

# Topics
""",
    "queries": """---
type: index
section: queries
updated: ""
---

# Queries
""",
    "daily-log": """---
type: index
section: daily-log
updated: ""
---

# Daily Log
""",
}
_RAW_NOTE_SECTIONS = (
    "Context",
    "Related Work",
    "Gap",
    "Proposal",
    "Key Results",
    "Discussion",
    "Next Steps",
)


def _now_date() -> str:
    return datetime.now().date().isoformat()


def paper_distill_root(vault_path: str) -> Path:
    return Path(vault_path).expanduser() / PAPER_DISTILL_ROOT


def _index_path(root: Path, key: str) -> Path:
    if key == "master":
        return root / "_index.md"
    if key == "wiki":
        return root / "wiki" / "_index.md"
    if key in {"inbox", "raw", "queries", "daily-log"}:
        return root / key / "_index.md"
    if key in {"raw_source", "raw_notes"}:
        return root / "raw" / key.split("_", 1)[1] / "_index.md"
    if key == "zotero":
        return root / "zotero" / "_index.md"
    if key == "zotero_imports":
        return root / "zotero" / "imports" / "_index.md"
    return root / "wiki" / key / "_index.md"


def ensure_vault_structure(vault_path: str) -> Path:
    root = paper_distill_root(vault_path)
    root.mkdir(parents=True, exist_ok=True)

    for rel in _SECTION_DIRS.values():
        (root / rel).mkdir(parents=True, exist_ok=True)

    for key, content in _INDEX_CONTENT.items():
        target = _index_path(root, key)
        if not target.exists():
            target.write_text(content, encoding="utf-8")

    return root


def _frontmatter_block(data: dict[str, Any]) -> str:
    payload = yaml.safe_dump(
        data,
        sort_keys=False,
        allow_unicode=True,
        default_flow_style=False,
    ).strip()
    return f"---\n{payload}\n---\n"


def write_markdown(path: Path, frontmatter: dict[str, Any], body: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(f"{_frontmatter_block(frontmatter)}\n{body.strip()}\n", encoding="utf-8")
    return path


def write_json(path: Path, payload: dict[str, Any]) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return path


def update_frontmatter(path: Path, updates: dict[str, Any]) -> None:
    content = path.read_text(encoding="utf-8")
    if not content.startswith("---\n"):
        raise ValueError(f"Missing frontmatter in {path}")

    _, remainder = content.split("---\n", 1)
    fm_text, body = remainder.split("\n---\n", 1)
    frontmatter = yaml.safe_load(fm_text) or {}
    frontmatter.update(updates)
    path.write_text(f"{_frontmatter_block(frontmatter)}\n{body.lstrip()}", encoding="utf-8")


def citekey_for_paper(paper: dict[str, Any]) -> str:
    surname = first_author_surname(paper) or "unknown"
    year = str(paper.get("year") or "nd")
    title_tokens = [token for token in normalise_title(str(paper.get("title", ""))).split() if len(token) > 2]
    keyword = title_tokens[0] if title_tokens else "paper"
    return f"{surname}{year}-{keyword}"


def inbox_note_path(vault_path: str, paper: dict[str, Any]) -> Path:
    root = ensure_vault_structure(vault_path)
    day_dir = root / "inbox" / _now_date()
    slug = (paper.get("paper_id") or "paper").replace(":", "-").replace("/", "-")
    return day_dir / f"{slug}.md"


def raw_source_path(vault_path: str, citekey: str) -> Path:
    root = ensure_vault_structure(vault_path)
    return root / "raw" / "source" / _now_date() / f"{citekey}.md"


def raw_source_sidecar_path(vault_path: str, citekey: str) -> Path:
    root = ensure_vault_structure(vault_path)
    return root / "raw" / "source" / _now_date() / f"{citekey}.assets.json"


def raw_note_path(vault_path: str, citekey: str) -> Path:
    root = ensure_vault_structure(vault_path)
    return root / "raw" / "notes" / _now_date() / f"{citekey}.md"


def build_inbox_body(paper: dict[str, Any]) -> str:
    return render_template("inbox-paper.md.j2", {
        "title": paper.get("title", "Untitled Paper"),
        "summary": paper.get("tldr") or "No TL;DR available yet.",
        "abstract": paper.get("abstract") or "Abstract unavailable.",
        "why_recommended": paper.get("why_recommended") or "Recommended by the current ranking pipeline.",
        "score_breakdown": paper.get("_score_breakdown", {}),
        "venue_raw": paper.get("venue_raw") or paper.get("venue") or "Unknown",
        "venue_normalized": paper.get("venue_normalized") or "Unknown",
        "venue_tier": paper.get("venue_tier") or "unknown",
        "venue_source": paper.get("venue_source") or paper.get("_venue_source") or paper.get("source") or "unknown",
        "best_topic": paper.get("best_topic") or "unknown",
        "doi": paper.get("doi") or "N/A",
        "canonical_html_url": paper.get("canonical_html_url") or "N/A",
        "canonical_pdf_url": paper.get("canonical_pdf_url") or paper.get("open_access_url") or "N/A",
        "canonical_item_url": paper.get("canonical_item_url") or "N/A",
    })


def build_raw_source_body(source_doc: Any) -> str:
    return str(getattr(source_doc, "markdown", "")).strip()


def build_raw_note_body(note_payload: dict[str, Any]) -> str:
    paper = note_payload.get("paper", {})
    sections = note_payload.get("sections", {})
    evidence = note_payload.get("evidence", {})
    return render_template("raw-note.md.j2", {
        "title": paper.get("title", "Untitled Paper"),
        "sections_order": list(_RAW_NOTE_SECTIONS),
        "sections": sections,
        "evidence": evidence,
        "zotero_mode": paper.get("zotero_mode") or "N/A",
        "zotero_status": paper.get("zotero_status") or "N/A",
        "zotero_uri": paper.get("zotero_uri") or "N/A",
        "zotero_import_path": paper.get("zotero_import_path") or "N/A",
        "source_raw_path": paper.get("source_raw_path") or "N/A",
        "source_structured_path": paper.get("source_structured_path") or "N/A",
        "canonical_html_url": paper.get("canonical_html_url") or "N/A",
        "canonical_pdf_url": paper.get("canonical_pdf_url") or "N/A",
        "capture_fidelity": paper.get("capture_fidelity") or "N/A",
    })


def build_raw_body(paper: dict[str, Any]) -> str:
    """Backward-compatible alias for the new note layer."""
    note_payload = {
        "paper": paper,
        "sections": {
            "Context": paper.get("summary") or paper.get("why_recommended") or "Approved from inbox.",
            "Related Work": paper.get("abstract") or "Abstract unavailable.",
            "Gap": paper.get("why_recommended") or "Gap not yet extracted.",
            "Proposal": paper.get("abstract") or "Proposal unavailable.",
            "Key Results": "Results unavailable in the legacy raw note format.",
            "Discussion": "Discussion unavailable in the legacy raw note format.",
            "Next Steps": "Regenerate this note through the v2.1 source capture pipeline for a higher-quality note.",
        },
        "evidence": {},
    }
    return build_raw_note_body(note_payload)
