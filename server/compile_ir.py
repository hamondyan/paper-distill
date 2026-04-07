"""Compile IR (Intermediate Representation) for the EDC pipeline.

The EDC pipeline has three stages:

    Extract  — agent reads raw notes, produces a structured IR JSON
    Resolve  — pure-Python entity-linking: candidate_concepts → registry IDs
    Write    — render IR to wiki markdown, update compile_state/compile_deps

This module handles schema validation, IR persistence, entity linking,
tension-signal aggregation, and the atomic Write step.
"""
from __future__ import annotations

import difflib
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
from server.vault_ops import (
    append_knowledge_log,
    compiled_ir_path,
    compiled_ir_resolved_path,
    normalize_knowledge_impact,
    paper_distill_root,
    refresh_global_navigation,
)

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
_OPTIONAL_TENSION_KEYS = {"failure_modes", "transfer_constraints"}
_USER_SECTION_RE = re.compile(r"^##\s+(My Notes|Reading Notes)\b", re.MULTILINE)
_MANAGED_BLOCK_RE = re.compile(
    r"<!--\s*managed:start(?:\s+section=([^\s>]+))?\s*-->\n?(.*?)\n?<!--\s*managed:end(?:.*?)-->",
    re.DOTALL,
)


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
            for k in _OPTIONAL_TENSION_KEYS:
                if k in tf and not isinstance(tf[k], list):
                    errors.append(f"tension_fields.{k} must be a list")
            for rich_key in ("limitations", "assumptions", "open_questions", "negative_results"):
                for item in tf.get(rich_key, []):
                    if isinstance(item, dict):
                        if "claim" not in item and "question" not in item:
                            errors.append(f"tension_fields.{rich_key} items must contain 'claim' or 'question'")
                        if "source_ref" in item and not isinstance(item["source_ref"], str):
                            errors.append(f"tension_fields.{rich_key}.source_ref must be a string")

            for rich_key in ("failure_modes", "transfer_constraints"):
                for item in tf.get(rich_key, []):
                    if isinstance(item, dict):
                        if "claim" not in item:
                            errors.append(f"tension_fields.{rich_key} items must contain 'claim'")
                        if "source_ref" in item and not isinstance(item["source_ref"], str):
                            errors.append(f"tension_fields.{rich_key}.source_ref must be a string")

    if "benchmark_scope" in ir_data and not isinstance(ir_data["benchmark_scope"], (str, dict)):
        errors.append("'benchmark_scope' must be a string or object")
    if "claimed_novelty" in ir_data and not isinstance(ir_data["claimed_novelty"], (str, dict)):
        errors.append("'claimed_novelty' must be a string or object")

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
    impact = normalize_knowledge_impact(
        {"created_pages": [str(dest.relative_to(Path(vault_path)))]}
    )
    append_knowledge_log(
        vault_path,
        event_type="compile-extract",
        title=f"Wrote IR for {citekey}",
        summary=f"Stored the Extract-stage IR for {citekey}.",
        impact=impact,
    )
    refresh_global_navigation(vault_path)
    return {"valid": True, "errors": [], "path": str(dest), "knowledge_impact": impact}


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

    impact = normalize_knowledge_impact(
        {
            "created_pages": [str(dest.relative_to(Path(vault_path)))],
            "concepts_canonicalized": [
                item["canonical_id"] for item in resolutions if item.get("canonical_id")
            ],
        }
    )
    append_knowledge_log(
        vault_path,
        event_type="compile-resolve",
        title=f"Resolved IR for {citekey}",
        summary=f"Linked candidate concepts for {citekey} into the canonical registry.",
        impact=impact,
    )
    refresh_global_navigation(vault_path)

    return {
        "resolved_count": len(resolutions),
        "registered_new": registered_new,
        "path": str(dest),
        "resolutions": resolutions,
        "knowledge_impact": impact,
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
    - ``failure_modes``:          flat list of failure modes
    - ``transfer_constraints``:   flat list of transfer constraints
    - ``benchmark_scopes``:       flat list of benchmark scope entries
    - ``claimed_novelties``:      flat list of claimed novelty entries
    """
    pd_root = paper_distill_root(vault_path)
    ir_dir = pd_root / "compiled_ir"
    if not ir_dir.exists():
        return {
            "recurring_limitations": [],
            "all_assumptions": [],
            "open_question_clusters": [],
            "negative_results": [],
            "failure_modes": [],
            "transfer_constraints": [],
            "benchmark_scopes": [],
            "claimed_novelties": [],
            "papers_scanned": 0,
        }

    limitation_index: dict[str, list[str]] = defaultdict(list)  # keyword → [citekey, ...]
    all_assumptions: list[dict] = []
    open_questions: list[dict] = []
    negative_results: list[dict] = []
    failure_modes: list[dict] = []
    transfer_constraints: list[dict] = []
    benchmark_scopes: list[dict] = []
    claimed_novelties: list[dict] = []
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

        for fm in tf.get("failure_modes", []):
            if isinstance(fm, dict):
                failure_modes.append({**fm, "paper": citekey})
            else:
                failure_modes.append({"claim": str(fm), "paper": citekey})

        for tc in tf.get("transfer_constraints", []):
            if isinstance(tc, dict):
                transfer_constraints.append({**tc, "paper": citekey})
            else:
                transfer_constraints.append({"claim": str(tc), "paper": citekey})

        benchmark_scope = ir.get("benchmark_scope")
        if benchmark_scope:
            if isinstance(benchmark_scope, dict):
                benchmark_scopes.append({**benchmark_scope, "paper": citekey})
            else:
                benchmark_scopes.append({"claim": str(benchmark_scope), "paper": citekey})

        claimed_novelty = ir.get("claimed_novelty")
        if claimed_novelty:
            if isinstance(claimed_novelty, dict):
                claimed_novelties.append({**claimed_novelty, "paper": citekey})
            else:
                claimed_novelties.append({"claim": str(claimed_novelty), "paper": citekey})

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
        "failure_modes": failure_modes,
        "transfer_constraints": transfer_constraints,
        "benchmark_scopes": benchmark_scopes,
        "claimed_novelties": claimed_novelties,
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

    dest = pd_root / rel_dir / f"{page_id}.md"

    conn = get_db(vault_path)
    existing_state = conn.execute(
        "SELECT * FROM compile_state WHERE page_id = ? AND page_type = ?",
        (page_id, page_type),
    ).fetchone()

    existed_before = dest.exists()
    current_body = ""
    if existed_before:
        current_body = _strip_frontmatter(dest.read_text(encoding="utf-8"))

    previous_managed_blocks = _decode_json_column(existing_state, "managed_blocks_json")
    previous_managed_hashes = _decode_json_column(existing_state, "managed_hashes_json")

    if existing_state and previous_managed_blocks and current_body:
        merged_body = _merge_existing_page(
            current_body=current_body,
            new_body=content,
            previous_managed_blocks=previous_managed_blocks,
            previous_managed_hashes=previous_managed_hashes,
        )
        if merged_body["conflict_detected"]:
            return {
                "written": False,
                "conflict_detected": True,
                "conflicts": merged_body["conflicts"],
                "path": str(dest),
            }
        final_body = merged_body["body"]
        final_managed_blocks = merged_body["managed_blocks"]
    else:
        final_body, final_managed_blocks = _initialise_or_replace_body(current_body, content)

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
    managed = _extract_managed_sections(final_body)
    content_hash = hashlib.sha256(managed.encode()).hexdigest()[:16]
    managed_hashes = {
        section: hashlib.sha256(block.encode()).hexdigest()[:16]
        for section, block in final_managed_blocks.items()
    }

    # Write file
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(f"{fm_block}\n\n{final_body.strip()}\n", encoding="utf-8")

    # Get current compile_version from DB if exists
    new_version = (existing_state["compile_version"] + 1) if existing_state else compile_version

    conn.execute(
        """INSERT OR REPLACE INTO compile_state
           (page_id, page_type, compile_version, schema_version, compiled_at,
            ir_path, content_hash, managed_hashes_json, managed_blocks_json)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (
            page_id,
            page_type,
            new_version,
            SCHEMA_VERSION,
            now,
            ir_path,
            content_hash,
            json.dumps(managed_hashes, ensure_ascii=False, sort_keys=True),
            json.dumps(final_managed_blocks, ensure_ascii=False, sort_keys=True),
        ),
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

    impact = normalize_knowledge_impact(
        {
            "created_pages": [] if existed_before else [str(dest.relative_to(pd_root.parent))],
            "updated_pages": [str(dest.relative_to(pd_root.parent))] if existed_before else [],
            "linked_pages": [
                f"{dep.get('dep_type', 'concept')}:{dep.get('dep_id', '')}"
                for dep in (deps or [])
                if dep.get("dep_id")
            ],
        }
    )
    append_knowledge_log(
        vault_path,
        event_type="compile-write",
        title=f"Committed {page_type} page {page_id}",
        summary=f"Wrote compiled {page_type} content and refreshed compile state for {page_id}.",
        impact=impact,
    )
    refresh_global_navigation(vault_path)

    return {
        "written": True,
        "path": str(dest),
        "compile_version": new_version,
        "content_hash": content_hash,
        "knowledge_impact": impact,
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
    blocks = _parse_managed_blocks(_split_user_suffix(content)[0])[1]
    if blocks:
        return "\n\n".join(blocks.values()).strip()
    return content


def _strip_frontmatter(text: str) -> str:
    if text.startswith("---\n"):
        end = text.find("\n---\n", 4)
        if end != -1:
            return text[end + 5 :].lstrip("\n")
    return text


def _decode_json_column(row: Any, key: str) -> dict[str, str]:
    if not row or not row[key]:
        return {}
    try:
        value = json.loads(row[key])
    except (TypeError, json.JSONDecodeError):
        return {}
    return value if isinstance(value, dict) else {}


def _split_user_suffix(body: str) -> tuple[str, str]:
    match = _USER_SECTION_RE.search(body)
    if not match:
        return body.strip(), ""
    return body[: match.start()].strip(), body[match.start() :].strip()


def _parse_managed_blocks(body: str) -> tuple[list[str], dict[str, str]]:
    order: list[str] = []
    blocks: dict[str, str] = {}
    for index, match in enumerate(_MANAGED_BLOCK_RE.finditer(body)):
        section = match.group(1) or f"section-{index}"
        order.append(section)
        blocks[section] = match.group(0).strip()
    if not blocks and body.strip():
        order = ["body"]
        blocks = {"body": body.strip()}
    return order, blocks


def _initialise_or_replace_body(current_body: str, new_body: str) -> tuple[str, dict[str, str]]:
    _legacy_main, user_suffix = _split_user_suffix(current_body)
    new_main, new_user_suffix = _split_user_suffix(new_body)
    preserved_user = user_suffix or new_user_suffix
    order, blocks = _parse_managed_blocks(new_main)
    rendered_main = "\n\n".join(blocks[section] for section in order if blocks.get(section)).strip()
    if preserved_user:
        if rendered_main:
            return f"{rendered_main}\n\n{preserved_user}".strip(), blocks
        return preserved_user.strip(), blocks
    return rendered_main, blocks


def _merge_existing_page(
    *,
    current_body: str,
    new_body: str,
    previous_managed_blocks: dict[str, str],
    previous_managed_hashes: dict[str, str],
) -> dict[str, Any]:
    current_main, user_suffix = _split_user_suffix(current_body)
    new_main, new_user_suffix = _split_user_suffix(new_body)
    current_order, current_blocks = _parse_managed_blocks(current_main)
    new_order, new_blocks = _parse_managed_blocks(new_main)
    preserved_user = user_suffix or new_user_suffix

    conflicts: list[str] = []
    merged_blocks: dict[str, str] = {}

    sections = list(dict.fromkeys([*new_order, *current_order, *previous_managed_blocks.keys()]))
    for section in sections:
        base = previous_managed_blocks.get(section, "")
        local = current_blocks.get(section, base)
        remote = new_blocks.get(section, "")

        # Fast-path with stored hash equivalence
        current_hash = hashlib.sha256(local.encode()).hexdigest()[:16] if local else ""
        if base and previous_managed_hashes.get(section) == current_hash:
            merged = remote
            conflict = False
        else:
            merged, conflict = _three_way_merge_text(base, local, remote)

        if conflict:
            conflicts.append(section)
            continue
        if merged:
            merged_blocks[section] = merged

    if conflicts:
        return {"conflict_detected": True, "conflicts": conflicts}

    rendered_main = "\n\n".join(
        merged_blocks[section] for section in new_order if section in merged_blocks
    ).strip()
    if preserved_user:
        if rendered_main:
            body = f"{rendered_main}\n\n{preserved_user}".strip()
        else:
            body = preserved_user.strip()
    else:
        body = rendered_main
    return {
        "conflict_detected": False,
        "conflicts": [],
        "body": body,
        "managed_blocks": merged_blocks,
    }


def _three_way_merge_text(base: str, local: str, remote: str) -> tuple[str, bool]:
    if local == remote:
        return local, False
    if local == base:
        return remote, False
    if remote == base:
        return local, False
    if not base:
        return "", True
    merged_lines = _three_way_merge_lines(
        base.splitlines(keepends=True),
        local.splitlines(keepends=True),
        remote.splitlines(keepends=True),
    )
    if merged_lines is None:
        return "", True
    return "".join(merged_lines).strip(), False


def _three_way_merge_lines(
    base_lines: list[str],
    local_lines: list[str],
    remote_lines: list[str],
) -> list[str] | None:
    local_changes = _diff_changes(base_lines, local_lines)
    remote_changes = _diff_changes(base_lines, remote_lines)

    combined: list[tuple[int, int, list[str], str]] = []
    for change in local_changes + remote_changes:
        overlap = next((existing for existing in combined if _changes_overlap(existing, change)), None)
        if overlap:
            if overlap[0] == change[0] and overlap[1] == change[1] and overlap[2] == change[2]:
                continue
            return None
        combined.append(change)

    result = list(base_lines)
    for start, end, replacement, _origin in sorted(combined, key=lambda item: (item[0], item[1]), reverse=True):
        result[start:end] = replacement
    return result


def _diff_changes(base_lines: list[str], other_lines: list[str]) -> list[tuple[int, int, list[str], str]]:
    matcher = difflib.SequenceMatcher(a=base_lines, b=other_lines)
    changes: list[tuple[int, int, list[str], str]] = []
    for tag, i1, i2, j1, j2 in matcher.get_opcodes():
        if tag == "equal":
            continue
        changes.append((i1, i2, other_lines[j1:j2], tag))
    return changes


def _changes_overlap(
    left: tuple[int, int, list[str], str],
    right: tuple[int, int, list[str], str],
) -> bool:
    l_start, l_end = left[0], left[1]
    r_start, r_end = right[0], right[1]
    if l_start == l_end == r_start == r_end:
        return True
    return max(l_start, r_start) < min(l_end, r_end) or (l_start == l_end and r_start <= l_start <= r_end) or (r_start == r_end and l_start <= r_start <= l_end)
