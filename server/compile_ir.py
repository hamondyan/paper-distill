"""Compile IR (Intermediate Representation) for the EDC pipeline.

The EDC pipeline has three stages:

    Extract  — agent reads raw notes, produces a structured IR JSON
    Resolve  — pure-Python entity-linking: candidate_concepts → registry IDs
    Write    — render IR to wiki markdown, update compile_state/compile_deps

This module handles schema validation, IR persistence, entity linking,
tension-signal aggregation, and the atomic Write step.
"""
from __future__ import annotations

import hashlib
import json
import logging
import os
import re
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from typing import Any

from server.database import get_db
from server.vault_ops import compiled_ir_path, compiled_ir_resolved_path, paper_distill_root

LOG = logging.getLogger(__name__)

SCHEMA_VERSION = "2024-06"

_TYPE_DIR = {
    "paper": "wiki/papers",
    "concept": "wiki/concepts",
    "method": "wiki/methods",
    "topic": "wiki/topics",
}

# ---------------------------------------------------------------------------
# IR Schema (required top-level keys)
# ---------------------------------------------------------------------------

_REQUIRED_KEYS = {
    "citekey",
    "title",
    "authors",
    "tension_fields",
    "candidate_concepts",
}

_REQUIRED_TENSION_KEYS = {"limitations", "assumptions", "open_questions", "negative_results"}


def validate_ir(ir_data: dict) -> list[str]:
    """Validate IR dict against the schema.  Returns list of error strings."""
    errors: list[str] = []
    for key in _REQUIRED_KEYS:
        if key not in ir_data:
            errors.append(f"Missing required field: '{key}'")

    if "tension_fields" in ir_data:
        tf = ir_data["tension_fields"]
        if not isinstance(tf, dict):
            errors.append("'tension_fields' must be an object")
        else:
            for k in _REQUIRED_TENSION_KEYS:
                if k not in tf:
                    errors.append(f"tension_fields missing key: '{k}'")
                elif not isinstance(tf[k], list):
                    errors.append(f"tension_fields.{k} must be a list")

    if "candidate_concepts" in ir_data and not isinstance(ir_data["candidate_concepts"], list):
        errors.append("'candidate_concepts' must be a list")

    return errors


# ---------------------------------------------------------------------------
# Write / Read IR
# ---------------------------------------------------------------------------

def write_ir(vault_path: str, citekey: str, ir_data: dict) -> dict[str, Any]:
    """Validate and persist the raw Extract IR.

    The IR is written to ``compiled_ir/{citekey}.json`` inside the vault.
    A ``schema_version`` field is injected if absent.

    Returns a result dict with ``path``, ``valid`` (bool), and ``errors``.
    """
    errors = validate_ir(ir_data)
    if errors:
        return {"valid": False, "errors": errors}

    ir_data = dict(ir_data)
    ir_data.setdefault("schema_version", SCHEMA_VERSION)
    ir_data.setdefault("ir_type", "paper")

    dest = compiled_ir_path(vault_path, citekey)
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(json.dumps(ir_data, ensure_ascii=False, indent=2), encoding="utf-8")

    LOG.info("Wrote IR for %s → %s", citekey, dest)
    return {"valid": True, "errors": [], "path": str(dest)}


def read_ir(vault_path: str, citekey: str, resolved: bool = False) -> dict | None:
    """Read an IR JSON.  Returns None if not found."""
    path = compiled_ir_resolved_path(vault_path, citekey) if resolved else compiled_ir_path(vault_path, citekey)
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as exc:
        LOG.warning("Failed to read IR %s: %s", path, exc)
        return None


# ---------------------------------------------------------------------------
# Resolve: entity linking via concept registry
# ---------------------------------------------------------------------------

def resolve_ir(vault_path: str, citekey: str) -> dict[str, Any]:
    """Resolve candidate_concepts in the raw IR against the concept registry.

    Reads ``compiled_ir/{citekey}.json``, maps each candidate concept to its
    canonical registry entry (registering new ones as needed), and writes the
    result to ``compiled_ir/{citekey}_resolved.json``.

    Returns a summary dict with ``resolved_count``, ``registered_new``,
    ``path``, and per-concept ``resolutions``.
    """
    from server.concept_registry import register_concept, resolve_concept

    ir_data = read_ir(vault_path, citekey, resolved=False)
    if ir_data is None:
        return {"error": f"IR not found for citekey '{citekey}'"}

    resolved_data = dict(ir_data)
    resolutions: list[dict] = []
    registered_new = 0

    for item in ir_data.get("candidate_concepts", []):
        name = item.get("name", "")
        if not name:
            continue
        c_type = item.get("type", "concept")
        aliases = item.get("aliases", [])

        # Try to resolve first; if not found, register
        existing = resolve_concept(vault_path, name)
        if existing:
            canonical_id = existing["id"]
            canonical_name = existing["canonical"]
            is_new = False
        else:
            reg_result = register_concept(vault_path, name, c_type, aliases or None)
            canonical_id = reg_result["id"]
            canonical_name = reg_result["canonical"]
            is_new = reg_result.get("created", False)
            if is_new:
                registered_new += 1

        resolutions.append({
            "surface_form": name,
            "canonical_id": canonical_id,
            "canonical_name": canonical_name,
            "is_new": is_new,
        })

    resolved_data["_resolved"] = True
    resolved_data["_resolutions"] = resolutions

    dest = compiled_ir_resolved_path(vault_path, citekey)
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(json.dumps(resolved_data, ensure_ascii=False, indent=2), encoding="utf-8")

    return {
        "resolved_count": len(resolutions),
        "registered_new": registered_new,
        "path": str(dest),
        "resolutions": resolutions,
    }


# ---------------------------------------------------------------------------
# Tension signal aggregation
# ---------------------------------------------------------------------------

def aggregate_tension_signals(
    vault_path: str,
    min_occurrence: int = 2,
    topic_filter: str | None = None,
) -> dict[str, Any]:
    """Scan all resolved IRs and aggregate tension_fields.

    Returns:
    - ``recurring_limitations``:  limitations claimed in ≥ min_occurrence papers
    - ``all_assumptions``:        flat list for LLM conflict detection
    - ``open_question_clusters``: questions grouped by shared keywords
    - ``negative_results``:       flat list of negative results
    """
    pd_root = paper_distill_root(vault_path)
    ir_dir = pd_root / "compiled_ir"
    if not ir_dir.exists():
        return {
            "recurring_limitations": [],
            "all_assumptions": [],
            "open_question_clusters": [],
            "negative_results": [],
            "papers_scanned": 0,
        }

    limitation_index: dict[str, list[str]] = defaultdict(list)  # keyword → [citekey, ...]
    all_assumptions: list[dict] = []
    open_questions: list[dict] = []
    negative_results: list[dict] = []
    papers_scanned = 0

    for path in sorted(ir_dir.glob("*_resolved.json")):
        citekey = path.stem.replace("_resolved", "")
        try:
            ir = json.loads(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            continue

        # Optional topic filter
        if topic_filter:
            paper_topics = ir.get("topics", [])
            if isinstance(paper_topics, str):
                paper_topics = [paper_topics]
            if topic_filter.lower() not in [t.lower() for t in paper_topics]:
                continue

        papers_scanned += 1
        tf = ir.get("tension_fields", {})

        # Limitations → keyword index
        for lim in tf.get("limitations", []):
            claim = lim.get("claim", "") if isinstance(lim, dict) else str(lim)
            for kw in _extract_keywords(claim):
                limitation_index[kw].append(citekey)

        # Assumptions (flat, for LLM)
        for assumption in tf.get("assumptions", []):
            if isinstance(assumption, dict):
                all_assumptions.append({**assumption, "paper": citekey})
            else:
                all_assumptions.append({"claim": str(assumption), "paper": citekey})

        # Open questions
        for oq in tf.get("open_questions", []):
            if isinstance(oq, dict):
                open_questions.append({**oq, "paper": citekey})
            else:
                open_questions.append({"question": str(oq), "paper": citekey})

        # Negative results
        for nr in tf.get("negative_results", []):
            if isinstance(nr, dict):
                negative_results.append({**nr, "paper": citekey})
            else:
                negative_results.append({"claim": str(nr), "paper": citekey})

    # Recurring limitations: keywords in ≥ min_occurrence papers
    recurring: list[dict] = []
    seen_keywords: set[str] = set()
    for kw, papers in sorted(limitation_index.items(), key=lambda x: -len(x[1])):
        unique_papers = list(dict.fromkeys(papers))  # preserve order, deduplicate
        if len(unique_papers) >= min_occurrence and kw not in seen_keywords:
            seen_keywords.add(kw)
            recurring.append({"keyword": kw, "count": len(unique_papers), "papers": unique_papers[:10]})

    # Open question clustering by shared leading keywords
    clusters = _cluster_open_questions(open_questions)

    return {
        "recurring_limitations": recurring[:20],
        "all_assumptions": all_assumptions,
        "open_question_clusters": clusters[:10],
        "negative_results": negative_results,
        "papers_scanned": papers_scanned,
    }


def _extract_keywords(text: str) -> list[str]:
    """Extract content keywords (length > 4) from a limitation claim."""
    stopwords = {
        "this", "that", "with", "from", "have", "been", "their", "they",
        "only", "does", "more", "when", "which", "cannot", "could", "would",
        "also", "each", "into", "than", "these", "those", "such", "both",
    }
    words = re.findall(r"[a-z]{5,}", text.lower())
    return [w for w in words if w not in stopwords]


def _cluster_open_questions(questions: list[dict]) -> list[dict]:
    """Cluster open questions by shared leading keywords."""
    buckets: dict[str, list[dict]] = defaultdict(list)
    for q in questions:
        text = q.get("question", q.get("claim", ""))
        words = re.findall(r"[a-z]{4,}", text.lower())
        key = " ".join(sorted(set(words[:6]))) if words else "misc"
        buckets[key].append(q)

    clusters = []
    for theme, items in sorted(buckets.items(), key=lambda x: -len(x[1])):
        if len(items) >= 1:
            clusters.append({
                "theme": theme,
                "count": len(items),
                "questions": items[:5],
                "papers": list(dict.fromkeys(q["paper"] for q in items))[:10],
            })
    return clusters


# ---------------------------------------------------------------------------
# Commit compile result (atomic Write step)
# ---------------------------------------------------------------------------

def commit_compile_result(
    vault_path: str,
    page_id: str,
    page_type: str,
    content: str,
    frontmatter: dict,
    ir_path: str | None = None,
    deps: list[dict] | None = None,
) -> dict[str, Any]:
    """Atomic Write step: persist markdown + update compile_state/compile_deps.

    This is the sole exit point for the EDC Write stage.  Unlike
    ``upsert_wiki_article`` (generic safe write), this function:
    - Writes the managed-section content to the vault
    - Computes content_hash for the managed sections
    - Upserts compile_state and compile_deps in SQLite

    Parameters
    ----------
    page_id : str
        Logical identifier (citekey for papers, slug for concepts/topics).
    page_type : str
        "paper" | "concept" | "method" | "topic"
    content : str
        Full markdown body (frontmatter is added separately).
    frontmatter : dict
        Frontmatter fields to render.
    ir_path : str | None
        Path to the compiled IR JSON (resolved version preferred).
    deps : list[dict] | None
        Dependencies: each dict has ``dep_type``, ``dep_id``, ``dep_version``.
    """
    pd_root = paper_distill_root(vault_path)
    rel_dir = _TYPE_DIR.get(page_type)
    if not rel_dir:
        return {"error": f"Unknown page_type: '{page_type}'"}

    # Build frontmatter block
    fm_lines = ["---"]
    for k, v in frontmatter.items():
        if isinstance(v, list):
            fm_lines.append(f"{k}:")
            for item in v:
                fm_lines.append(f"  - {item}")
        elif isinstance(v, dict):
            fm_lines.append(f"{k}: {json.dumps(v)}")
        else:
            # Escape simple values
            safe_v = str(v).replace('"', '\\"')
            fm_lines.append(f'{k}: "{safe_v}"')
    fm_lines.append("---")
    fm_block = "\n".join(fm_lines)

    now = datetime.now().isoformat(timespec="seconds")
    compile_version = frontmatter.get("compile_version", 1)
    if isinstance(compile_version, str):
        try:
            compile_version = int(compile_version)
        except ValueError:
            compile_version = 1

    # Compute content hash of managed sections
    managed = _extract_managed_sections(content)
    content_hash = hashlib.sha256(managed.encode()).hexdigest()[:16]

    # Write file
    dest = pd_root / rel_dir / f"{page_id}.md"
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(f"{fm_block}\n\n{content}", encoding="utf-8")

    # Update DB
    conn = get_db(vault_path)

    # Get current compile_version from DB if exists
    existing = conn.execute(
        "SELECT compile_version FROM compile_state WHERE page_id = ? AND page_type = ?",
        (page_id, page_type),
    ).fetchone()
    new_version = (existing["compile_version"] + 1) if existing else compile_version

    conn.execute(
        """INSERT OR REPLACE INTO compile_state
           (page_id, page_type, compile_version, schema_version, compiled_at,
            ir_path, content_hash)
           VALUES (?, ?, ?, ?, ?, ?, ?)""",
        (page_id, page_type, new_version, SCHEMA_VERSION, now, ir_path, content_hash),
    )

    # Clear and re-insert deps
    if deps:
        conn.execute(
            "DELETE FROM compile_deps WHERE page_id = ? AND page_type = ?",
            (page_id, page_type),
        )
        for dep in deps:
            conn.execute(
                """INSERT OR IGNORE INTO compile_deps
                   (page_id, page_type, dep_type, dep_id, dep_version)
                   VALUES (?, ?, ?, ?, ?)""",
                (page_id, page_type, dep.get("dep_type", "concept"),
                 dep["dep_id"], dep.get("dep_version", 1)),
            )

    conn.commit()

    return {
        "written": True,
        "path": str(dest),
        "compile_version": new_version,
        "content_hash": content_hash,
    }


def get_compile_state(vault_path: str, page_id: str, page_type: str = "paper") -> dict | None:
    """Look up compile state for a page."""
    conn = get_db(vault_path)
    row = conn.execute(
        "SELECT * FROM compile_state WHERE page_id = ? AND page_type = ?",
        (page_id, page_type),
    ).fetchone()
    return dict(row) if row else None


def _extract_managed_sections(content: str) -> str:
    """Extract text between <!-- managed:start --> and <!-- managed:end -->."""
    match = re.search(
        r"<!--\s*managed:start\s*-->(.+?)<!--\s*managed:end\s*-->",
        content,
        re.DOTALL,
    )
    return match.group(1).strip() if match else content
