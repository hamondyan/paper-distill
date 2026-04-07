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
    "compiled_ir": "compiled_ir",
    "state": ".state",
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
_KNOWLEDGE_IMPACT_KEYS = (
    "created_pages",
    "updated_pages",
    "linked_pages",
    "concepts_canonicalized",
    "topics_refreshed",
    "queries_saved",
    "maintenance_tasks_created",
    "conflicts_or_skips",
)


def _now_date() -> str:
    return datetime.now().date().isoformat()


def paper_distill_root(vault_path: str) -> Path:
    return Path(vault_path).expanduser() / PAPER_DISTILL_ROOT


def global_index_path(vault_path: str) -> Path:
    return paper_distill_root(vault_path) / "index.md"


def knowledge_log_path(vault_path: str) -> Path:
    return paper_distill_root(vault_path) / "log.md"


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

    # Initialize SQLite database
    from server.database import init_db
    init_db(vault_path)

    index_path = root / "index.md"
    if not index_path.exists():
        index_path.write_text(
            "# Paper Distill Index\n\nKnowledge map coming online. Run an ingest, query, compile, or maintenance action to refresh this overview.\n",
            encoding="utf-8",
        )

    log_path = root / "log.md"
    if not log_path.exists():
        log_path.write_text(
            "# Paper Distill Log\n\nAppend-only timeline of ingest, query, compile, maintenance, and idea activity.\n",
            encoding="utf-8",
        )

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


def compiled_ir_path(vault_path: str, citekey: str) -> Path:
    """Return path for the raw Extract IR JSON."""
    root = paper_distill_root(vault_path)
    return root / "compiled_ir" / f"{citekey}.json"


def compiled_ir_resolved_path(vault_path: str, citekey: str) -> Path:
    """Return path for the Resolved IR JSON."""
    root = paper_distill_root(vault_path)
    return root / "compiled_ir" / f"{citekey}_resolved.json"


def state_db_path(vault_path: str) -> Path:
    """Return path to the SQLite database."""
    root = paper_distill_root(vault_path)
    return root / ".state" / "paper-distill.db"


def normalize_knowledge_impact(impact: dict[str, Any] | None = None) -> dict[str, list[Any]]:
    payload = dict(impact or {})
    normalized: dict[str, list[Any]] = {}
    for key in _KNOWLEDGE_IMPACT_KEYS:
        value = payload.get(key, [])
        if value is None:
            normalized[key] = []
        elif isinstance(value, list):
            normalized[key] = value
        else:
            normalized[key] = [value]
    return normalized


def build_knowledge_impact_summary(impact: dict[str, Any]) -> str:
    normalized = normalize_knowledge_impact(impact)
    sections = []
    for key in _KNOWLEDGE_IMPACT_KEYS:
        if normalized[key]:
            sections.append((key, normalized[key]))
    return render_template(
        "knowledge-impact-summary.md.j2",
        {
            "sections": sections,
            "has_any": bool(sections),
        },
    )


def build_query_asset_frontmatter(
    *,
    note_type: str,
    title: str,
    question: str,
    source_pages: list[str] | None = None,
    papers_referenced: list[str] | None = None,
    concepts_referenced: list[str] | None = None,
    topics_referenced: list[str] | None = None,
    derived_actions: list[str] | None = None,
    promotion_targets: list[dict[str, Any]] | None = None,
    status: str = "saved",
) -> dict[str, Any]:
    return {
        "type": note_type,
        "title": title,
        "question": question,
        "date": _now_date(),
        "source_pages": list(source_pages or []),
        "papers_referenced": list(papers_referenced or []),
        "concepts_referenced": list(concepts_referenced or []),
        "topics_referenced": list(topics_referenced or []),
        "derived_actions": list(derived_actions or []),
        "promotion_targets": list(promotion_targets or []),
        "status": status,
    }


def build_query_asset_body(payload: dict[str, Any]) -> str:
    return render_template(
        "query-note.md.j2",
        {
            "title": payload.get("title", "Untitled Query Asset"),
            "question": payload.get("question", ""),
            "summary": payload.get("summary", "Summary not provided yet."),
            "answer": payload.get("answer", ""),
            "source_pages": list(payload.get("source_pages", [])),
            "promotion_targets": list(payload.get("promotion_targets", [])),
            "derived_actions": list(payload.get("derived_actions", [])),
        },
    )


def _read_frontmatter(path: Path) -> dict[str, Any]:
    try:
        content = path.read_text(encoding="utf-8")
    except OSError:
        return {}
    if not content.startswith("---\n"):
        return {}
    _, remainder = content.split("---\n", 1)
    if "\n---\n" not in remainder:
        return {}
    fm_text, _body = remainder.split("\n---\n", 1)
    frontmatter = yaml.safe_load(fm_text) or {}
    return frontmatter if isinstance(frontmatter, dict) else {}


def _recent_items(directory: Path, *, limit: int = 5, title_key: str = "title") -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    if not directory.exists():
        return items
    for path in directory.rglob("*.md"):
        if path.name == "_index.md":
            continue
        fm = _read_frontmatter(path)
        try:
            mtime = path.stat().st_mtime
        except OSError:
            mtime = 0.0
        items.append(
            {
                "path": str(path),
                "relative_path": str(path.relative_to(directory.parents[0])),
                "title": str(fm.get(title_key) or fm.get("title") or path.stem),
                "type": str(fm.get("type", "")),
                "mtime": mtime,
            }
        )
    items.sort(key=lambda item: item["mtime"], reverse=True)
    return items[:limit]


def refresh_global_navigation(vault_path: str) -> Path:
    root = ensure_vault_structure(vault_path)

    from server.maintenance import get_pending_tasks
    from server.vault_query import query_vault_sync

    all_sections = query_vault_sync(vault_path, section="all", detail="full")
    queries = _recent_items(root / "queries", limit=5)
    concepts = _recent_items(root / "wiki" / "concepts", limit=5, title_key="concept")
    topics = _recent_items(root / "wiki" / "topics", limit=5, title_key="topic")
    pending_tasks = get_pending_tasks(vault_path)
    uncompiled = query_vault_sync(vault_path, section="raw_notes", uncompiled_only=True, detail="full")

    body = render_template(
        "global-index.md.j2",
        {
            "date": _now_date(),
            "stats": all_sections.get("stats", {}),
            "recent_queries": queries,
            "recent_concepts": concepts,
            "recent_topics": topics,
            "pending_maintenance_count": len(pending_tasks),
            "uncompiled_count": uncompiled.get("stats", {}).get("raw_notes", 0),
        },
    )
    global_index_path(vault_path).write_text(body, encoding="utf-8")
    return global_index_path(vault_path)


def append_knowledge_log(
    vault_path: str,
    *,
    event_type: str,
    title: str,
    summary: str,
    impact: dict[str, Any] | None = None,
) -> Path:
    root = ensure_vault_structure(vault_path)
    log_path = root / "log.md"
    normalized = normalize_knowledge_impact(impact)
    impact_count = sum(len(items) for items in normalized.values())
    entry = (
        f"\n## [{datetime.now().isoformat(timespec='seconds')}] {event_type} | {title}\n\n"
        f"{summary}\n\n"
        f"- Impact count: {impact_count}\n\n"
        f"{build_knowledge_impact_summary(normalized).strip()}\n"
    )
    with log_path.open("a", encoding="utf-8") as handle:
        handle.write(entry)
    return log_path


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


def build_raw_source_body(source_doc: Any, source_structured_path: str = "") -> str:
    body = str(getattr(source_doc, "markdown", "")).strip()
    figures = list(getattr(source_doc, "figures", []) or [])
    tables = list(getattr(source_doc, "tables", []) or [])
    equations = list(getattr(source_doc, "equations", []) or [])
    if not (figures or tables or equations):
        return body

    index_lines = [
        "## Captured Assets Index",
        "",
        f"- Figures captured: {len(figures)}",
        f"- Tables captured: {len(tables)}",
        f"- Equations captured: {len(equations)}",
    ]
    if source_structured_path:
        index_lines.append(f"- Structured data: {source_structured_path}")

    if "## Captured Assets Index" in body:
        if source_structured_path and f"- Structured data: {source_structured_path}" not in body:
            body = f"{body}\n- Structured data: {source_structured_path}"
        return body

    index_block = "\n".join(index_lines).strip()
    if not body:
        return index_block
    return f"{body}\n\n{index_block}"


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
