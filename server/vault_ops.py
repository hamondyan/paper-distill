"""Helpers for initializing and writing Paper Distill vault notes."""
from __future__ import annotations

import json
import logging
import re
from datetime import datetime
from pathlib import Path
from typing import Any

import yaml

from server.paper_utils import first_author_surname, normalise_title
from server.template_render import render_template
from server.vault_contract import (
    PAPER_DISTILL_ROOT,
    ROOT_DIRS,
    paper_distill_root,
    root_path,
    root_rel_path,
    template_contract_context,
)

LOG = logging.getLogger(__name__)

_SECTION_DIRS = dict(ROOT_DIRS)

_INDEX_CONTENT = {
    "master": """---
type: index
section: master
updated: ""
---

# Paper Distill

Research knowledge system with human approval, evidence-first source capture, insight assets, and AI-maintained wiki layers.

## Sections

- `inbox/` candidate papers awaiting review
- `sources/evidence/` source-grounded evidence captures
- `wiki/papers/` canonical paper work pages
- `wiki/` compiled knowledge pages
- `insights/` saved digests, query assets, ideas, and dialogue artifacts
  plus memory promotion audit notes
- `memory/` current-view advisory memory surfaces
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
    "sources": """---
type: index
section: sources
updated: ""
---

# Sources

Evidence-first source layer for approved papers.

- `evidence/` holds cleaned source captures plus sidecars
""",
    "sources_evidence": """---
type: index
section: sources/evidence
updated: ""
---

# Source Evidence

Cleaned source captures. This is the stable evidence layer.
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

Compiled knowledge derived only from approved source evidence and hidden IR.
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
    "insights": """---
type: index
section: insights
updated: ""
---

# Insights

Saved research-facing outputs that are not canonical wiki pages.
""",
    "queries": """---
type: index
section: insights/queries
updated: ""
---

# Query Assets
""",
    "ideas": """---
type: index
section: insights/ideas
updated: ""
---

# Ideas
""",
    "dialogues": """---
type: index
section: insights/dialogues
updated: ""
---

# Dialogues
""",
    "memory_promotions": """---
type: index
section: insights/memory-promotions
updated: ""
---

# Memory Promotions
""",
    "digests": """---
type: index
section: insights/digests
updated: ""
---

# Digests
""",
    "memory": """---
type: index
section: memory
updated: ""
---

# Memory
""",
}
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


def knowledge_log_path(vault_path: str) -> Path:
    return paper_distill_root(vault_path) / "log.md"


def _index_path(root: Path, key: str) -> Path:
    if key == "master":
        return root / "_index.md"
    return root / root_rel_path(key) / "_index.md"


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
            "# Paper Distill\n\nUse the MCP tools for library state and queries. This note is only a human landing page.\n",
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


_PAGE_ASSET_ROOTS = {
    "paper": "papers",
    "concept": "concepts",
    "method": "methods",
    "topic": "topics",
    "query": "queries",
}


def _page_asset_path(vault_path: str, page_id: str, page_type: str) -> Path | None:
    root_key = _PAGE_ASSET_ROOTS.get(page_type)
    if root_key is None:
        return None
    return root_path(vault_path, root_key) / f"{page_id}.md"


def _read_markdown_note(path: Path) -> tuple[dict[str, Any], str]:
    content = path.read_text(encoding="utf-8")
    if not content.startswith("---\n"):
        return {}, content.strip()
    _, remainder = content.split("---\n", 1)
    fm_text, body = remainder.split("\n---\n", 1)
    frontmatter = yaml.safe_load(fm_text) or {}
    return (frontmatter if isinstance(frontmatter, dict) else {}), body.lstrip()


def _split_user_body(body: str) -> tuple[str, str]:
    match = re.search(r"^##\s+(My Notes|Reading Notes)\b", body, re.MULTILINE)
    if not match:
        return body.strip(), ""
    return body[: match.start()].strip(), body[match.start() :].strip()


def _replace_wikilinks(text: str, from_id: str, to_id: str, *, to_section: str) -> str:
    pattern = re.compile(rf"\[\[(concepts|topics)/{re.escape(from_id)}(?:\|([^\]]+))?\]\]")

    def repl(match: re.Match[str]) -> str:
        label = match.group(2)
        if label:
            return f"[[{to_section}/{to_id}|{label}]]"
        return f"[[{to_section}/{to_id}]]"

    return pattern.sub(repl, text)


def rewrite_page_asset_links(
    vault_path: str,
    page_id: str,
    page_type: str,
    from_id: str,
    to_id: str,
    *,
    to_section: str = "concepts",
) -> Path | None:
    """Rewrite concept/topic references for a visible page asset."""
    from server.concept_registry import slugify

    path = _page_asset_path(vault_path, page_id, page_type)
    if path is None or not path.exists():
        return None

    frontmatter, body = _read_markdown_note(path)
    main_body, user_suffix = _split_user_body(body)
    main_body = _replace_wikilinks(main_body, from_id, to_id, to_section=to_section)

    if page_type in {"paper", "concept", "topic"}:
        concepts = frontmatter.get("concepts", [])
        if isinstance(concepts, str):
            concepts = [concepts]
        concepts = [to_id if slugify(str(item)) == from_id else item for item in concepts]
        if concepts:
            frontmatter["concepts"] = concepts

        topics = frontmatter.get("topics", [])
        if isinstance(topics, str):
            topics = [topics]
        topics = [
            to_id if slugify(str(item)) == from_id and to_section == "topics" else item
            for item in topics
        ]
        if topics:
            frontmatter["topics"] = topics
    elif page_type == "query":
        concepts_referenced = frontmatter.get("concepts_referenced") or []
        if isinstance(concepts_referenced, str):
            concepts_referenced = [concepts_referenced]
        topics_referenced = frontmatter.get("topics_referenced") or []
        if isinstance(topics_referenced, str):
            topics_referenced = [topics_referenced]

        if to_section == "topics":
            concepts_referenced = [
                item for item in concepts_referenced if slugify(str(item)) != from_id
            ]
            if to_id not in topics_referenced:
                topics_referenced.append(to_id)
        else:
            concepts_referenced = [
                to_id if slugify(str(item)) == from_id else item for item in concepts_referenced
            ]
            topics_referenced = [
                to_id if slugify(str(item)) == from_id else item for item in topics_referenced
            ]

        frontmatter["concepts_referenced"] = concepts_referenced
        frontmatter["topics_referenced"] = topics_referenced

        promotion_targets = list(frontmatter.get("promotion_targets", []) or [])
        for target in promotion_targets:
            if not isinstance(target, dict):
                continue
            if slugify(str(target.get("page_id", ""))) != from_id:
                continue
            target["page_id"] = to_id
            if to_section == "topics":
                target["page_type"] = "topic"
        if promotion_targets:
            frontmatter["promotion_targets"] = promotion_targets

    rebuilt = main_body.strip()
    if user_suffix:
        rebuilt = f"{rebuilt}\n\n{user_suffix}".strip()
    write_markdown(path, frontmatter, rebuilt)
    return path


def promote_concept_page_to_topic_asset(vault_path: str, concept_id: str) -> dict[str, str] | None:
    """Copy a concept page into topics/ and replace the concept page with a redirect note."""
    concept_path = _page_asset_path(vault_path, concept_id, "concept")
    topic_path = _page_asset_path(vault_path, concept_id, "topic")
    if concept_path is None or topic_path is None or not concept_path.exists():
        return None

    frontmatter, body = _read_markdown_note(concept_path)
    write_markdown(topic_path, frontmatter, body)
    concept_title = str(frontmatter.get("concept") or concept_id)
    write_markdown(
        concept_path,
        {"concept": concept_id, "redirect_to": f"topics/{concept_id}"},
        f"# {concept_title}\n\nPromoted to [[topics/{concept_id}]].",
    )
    return {
        "concept_path": str(concept_path),
        "topic_path": str(topic_path),
    }


def mark_inbox_capture_failed(
    path: Path,
    *,
    error: str,
    canonical_html_url: str = "",
    canonical_pdf_url: str = "",
) -> dict[str, str]:
    """Apply a capture-failed update to an inbox note through the inbox asset contract."""
    updates = {
        "capture_status": "failed",
        "capture_error": error,
        "canonical_html_url": canonical_html_url,
        "canonical_pdf_url": canonical_pdf_url,
    }
    update_frontmatter(path, updates)
    return updates


def mark_inbox_capture_succeeded(path: Path, updates: dict[str, Any]) -> dict[str, Any]:
    """Apply a successful capture update to an inbox note through the inbox asset contract."""
    update_frontmatter(path, updates)
    return dict(updates)


def citekey_for_paper(paper: dict[str, Any]) -> str:
    surname = first_author_surname(paper) or "unknown"
    year = str(paper.get("year") or "nd")
    title_tokens = [token for token in normalise_title(str(paper.get("title", ""))).split() if len(token) > 2]
    keyword = title_tokens[0] if title_tokens else "paper"
    return f"{surname}{year}-{keyword}"


def inbox_note_path(vault_path: str, paper: dict[str, Any]) -> Path:
    ensure_vault_structure(vault_path)
    day_dir = root_path(vault_path, "inbox") / _now_date()
    slug = (paper.get("paper_id") or "paper").replace(":", "-").replace("/", "-")
    return day_dir / f"{slug}.md"


def source_evidence_path(vault_path: str, citekey: str) -> Path:
    ensure_vault_structure(vault_path)
    return root_path(vault_path, "sources_evidence") / _now_date() / f"{citekey}.md"


def source_evidence_sidecar_path(vault_path: str, citekey: str) -> Path:
    ensure_vault_structure(vault_path)
    return root_path(vault_path, "sources_evidence") / _now_date() / f"{citekey}.assets.json"


def wiki_paper_path(vault_path: str, citekey: str) -> Path:
    ensure_vault_structure(vault_path)
    return root_path(vault_path, "papers") / f"{citekey}.md"


def compiled_ir_path(vault_path: str, citekey: str) -> Path:
    """Return path for the raw Extract IR JSON."""
    return root_path(vault_path, "state_ir") / f"{citekey}.json"


def compiled_ir_resolved_path(vault_path: str, citekey: str) -> Path:
    """Return path for the Resolved IR JSON."""
    return root_path(vault_path, "state_ir") / f"{citekey}_resolved.json"


def state_db_path(vault_path: str) -> Path:
    """Return path to the SQLite database."""
    return root_path(vault_path, "state") / "paper-distill.db"


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
            **template_contract_context(),
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
        "updated_at": datetime.now().isoformat(timespec="seconds"),
        "source_pages": list(source_pages or []),
        "papers_referenced": list(papers_referenced or []),
        "concepts_referenced": list(concepts_referenced or []),
        "topics_referenced": list(topics_referenced or []),
        "derived_actions": list(derived_actions or []),
        "promotion_targets": list(promotion_targets or []),
        "refresh_state": "fresh",
        "stale_dependencies": [],
        "refresh_reason": "",
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
            **template_contract_context(),
        },
    )


def save_query_asset(
    vault_path: str,
    *,
    asset_id: str | None = None,
    note_type: str,
    title: str,
    question: str,
    summary: str,
    answer: str,
    source_pages: list[str] | None = None,
    papers_referenced: list[str] | None = None,
    concepts_referenced: list[str] | None = None,
    topics_referenced: list[str] | None = None,
    derived_actions: list[str] | None = None,
    promotion_targets: list[dict[str, Any]] | None = None,
    status: str = "saved",
) -> dict[str, Any]:
    """Persist a query asset through compile-aware publish and register deps."""
    from server.compile_ir import commit_compile_result as commit_compiled_page
    from server.concept_registry import slugify

    effective_id = slugify(asset_id or title or question or "query-asset") or "query-asset"
    frontmatter = build_query_asset_frontmatter(
        note_type=note_type,
        title=title,
        question=question,
        source_pages=source_pages,
        papers_referenced=papers_referenced,
        concepts_referenced=concepts_referenced,
        topics_referenced=topics_referenced,
        derived_actions=derived_actions,
        promotion_targets=promotion_targets,
        status=status,
    )
    body = build_query_asset_body(
        {
            "title": title,
            "question": question,
            "summary": summary,
            "answer": answer,
            "source_pages": list(source_pages or []),
            "promotion_targets": list(promotion_targets or []),
            "derived_actions": list(derived_actions or []),
        }
    )
    deps = _query_asset_dependency_entries(
        vault_path,
        papers_referenced=papers_referenced,
        concepts_referenced=concepts_referenced,
        topics_referenced=topics_referenced,
    )
    result = commit_compiled_page(
        vault_path,
        effective_id,
        "query",
        body,
        frontmatter,
        deps=deps,
    )
    result.setdefault("asset_id", effective_id)
    if result.get("written"):
        impact = normalize_knowledge_impact(result.get("knowledge_impact"))
        query_rel_path = f"{PAPER_DISTILL_ROOT}/{ROOT_DIRS['queries']}/{effective_id}.md"
        if query_rel_path not in impact["queries_saved"]:
            impact["queries_saved"].append(query_rel_path)
        result["knowledge_impact"] = impact
    return result


def mark_query_asset_stale(
    vault_path: str,
    asset_id: str,
    *,
    changed_dependencies: list[str] | None = None,
    reason: str,
) -> dict[str, Any]:
    """Flag a saved query asset as stale after an upstream dependency changes."""
    path = root_path(vault_path, "queries") / f"{asset_id}.md"
    if not path.exists():
        return {"updated": False, "path": str(path), "reason": "missing"}

    frontmatter = _read_frontmatter(path)
    stale_dependencies = list(frontmatter.get("stale_dependencies") or [])
    for dep_id in changed_dependencies or []:
        if dep_id and dep_id not in stale_dependencies:
            stale_dependencies.append(dep_id)

    update_frontmatter(
        path,
        {
            "refresh_state": "stale",
            "stale_dependencies": stale_dependencies,
            "refresh_reason": reason,
            "updated_at": datetime.now().isoformat(timespec="seconds"),
        },
    )
    return {
        "updated": True,
        "path": str(path),
        "refresh_state": "stale",
        "stale_dependencies": stale_dependencies,
    }


def _query_asset_dependency_entries(
    vault_path: str,
    *,
    papers_referenced: list[str] | None = None,
    concepts_referenced: list[str] | None = None,
    topics_referenced: list[str] | None = None,
) -> list[dict[str, Any]]:
    deps: list[dict[str, Any]] = []
    seen: set[tuple[str, str]] = set()
    for dep_type, values in (
        ("paper", papers_referenced or []),
        ("concept", concepts_referenced or []),
        ("topic", topics_referenced or []),
    ):
        for raw_dep_id in values:
            dep_id = str(raw_dep_id or "").strip()
            if not dep_id:
                continue
            dep_key = (dep_type, dep_id)
            if dep_key in seen:
                continue
            seen.add(dep_key)
            deps.append(
                {
                    "dep_type": dep_type,
                    "dep_id": dep_id,
                    "dep_version": _dependency_version(vault_path, dep_type, dep_id),
                }
            )
    return deps


def _dependency_version(vault_path: str, dep_type: str, dep_id: str) -> int:
    from server.database import get_db

    conn = get_db(vault_path)
    if dep_type == "paper":
        row = conn.execute(
            """
            SELECT compile_version
            FROM compile_state
            WHERE page_id = ? AND page_type = 'paper'
            """,
            (dep_id,),
        ).fetchone()
        return int(row["compile_version"]) if row else 1

    if dep_type in {"concept", "method", "topic"}:
        row = conn.execute(
            """
            SELECT compile_version
            FROM compile_state
            WHERE page_id = ? AND page_type = ?
            """,
            (dep_id, dep_type),
        ).fetchone()
        if row:
            return int(row["compile_version"])

        row = conn.execute(
            """
            SELECT version
            FROM concept_registry
            WHERE id = ?
            """,
            (dep_id,),
        ).fetchone()
        if row:
            return int(row["version"])

    return 1


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
        **template_contract_context(),
    })


def build_source_evidence_body(source_doc: Any, source_structured_path: str = "") -> str:
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

def build_wiki_paper_body(note_payload: dict[str, Any]) -> str:
    paper = note_payload.get("paper", {})
    sections = note_payload.get("sections", {})
    return render_template(
        "wiki-paper.md.j2",
        {
            "title": paper.get("title", "Untitled Paper"),
            "authors_short": paper.get("authors_short", ""),
            "year": paper.get("year") or "n.d.",
            "venue": paper.get("venue", ""),
            "citekey": paper.get("citekey", ""),
            "source_evidence_path": paper.get("source_evidence_path", ""),
            "source_assets_path": paper.get("source_assets_path", ""),
            "zotero_link": paper.get("zotero_uri", ""),
            "page_state": paper.get("page_state", "auto"),
            "confidence": paper.get("confidence", 0.0),
            "why_read": paper.get("why_read", "Auto-generated from source evidence."),
            "summary": paper.get("summary", ""),
            "context": sections.get("Context", ""),
            "related_work": sections.get("Related Work", ""),
            "gap": sections.get("Gap", ""),
            "proposal": sections.get("Proposal", ""),
            "results": sections.get("Key Results", ""),
            "discussion": sections.get("Discussion", ""),
            "insights": paper.get("insights", ""),
            "connections": paper.get("connections", ""),
            "next_steps": sections.get("Next Steps", ""),
            **template_contract_context(),
        },
    )
