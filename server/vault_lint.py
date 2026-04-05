"""Deterministic vault health checks, statistics, and knowledge graph analysis.

Complements vault_query.py by providing structural analysis that does NOT
require LLM judgment — broken links, missing frontmatter, orphans, etc.
"""
from __future__ import annotations

import glob
import logging
import os
import re
from collections import Counter, defaultdict
from datetime import datetime
from typing import Any

from server.vault_query import _parse_frontmatter, query_vault_sync

LOG = logging.getLogger(__name__)

_WIKILINK_RE = re.compile(r"\[\[([^\]|]+)(?:\|[^\]]+)?\]\]")

_PD_ROOT = "Paper Distill"

# Required frontmatter fields per vault section.
_REQUIRED_FIELDS: dict[str, list[str]] = {
    "inbox": ["paper_id", "status"],
    "raw_source": ["paper_id"],
    "raw_notes": ["paper_id", "compiled"],
    "papers": ["citekey", "title"],
    "concepts": ["concept"],
    "methods": [],
    "topics": [],
}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _iter_md_files(root: str, rel_dir: str) -> list[str]:
    """Walk *rel_dir* under *root*, returning absolute paths of non-index .md files."""
    target = os.path.join(root, rel_dir)
    if not os.path.isdir(target):
        return []
    return [
        p
        for p in glob.glob(os.path.join(target, "**", "*.md"), recursive=True)
        if os.path.basename(p) != "_index.md"
    ]


def _read_full_text(filepath: str) -> str:
    """Read up to 32 KiB of a markdown file (enough for wikilink scanning)."""
    try:
        with open(filepath, "r", encoding="utf-8") as fh:
            return fh.read(32768)
    except (OSError, UnicodeDecodeError):
        return ""


def _extract_wikilinks(text: str) -> list[str]:
    """Return raw wikilink targets from markdown text."""
    return _WIKILINK_RE.findall(text)


def _normalise_link_target(target: str) -> str:
    """Normalise a wikilink target to a relative path fragment.

    Obsidian wikilinks can be bare names (``[[foo]]``) or paths
    (``[[concepts/diffusion-policy]]``).  We strip leading ``Paper Distill/``
    or ``wiki/`` prefixes so all targets are relative to the vault's wiki
    directory for matching purposes.
    """
    t = target.strip().replace("\\", "/")
    for prefix in ("Paper Distill/wiki/", "Paper Distill/", "wiki/"):
        if t.startswith(prefix):
            t = t[len(prefix):]
            break
    return t


# ---------------------------------------------------------------------------
# 1. lint_vault
# ---------------------------------------------------------------------------

def lint_vault_sync(vault_path: str) -> dict[str, Any]:
    """Run deterministic structural health checks on the vault.

    Returns a JSON-serialisable dict with check results.
    """
    pd_root = os.path.join(vault_path, _PD_ROOT)
    if not os.path.isdir(pd_root):
        return {"error": f"Paper Distill root not found at {pd_root}"}

    results: dict[str, Any] = {}

    # --- Broken backlinks & orphan analysis ---------------------------------
    # Build two maps:
    #   file_key  → set of outgoing link targets
    #   link_target → set of files that link to it
    wiki_dir = os.path.join(pd_root, "wiki")
    raw_notes_dir = os.path.join(pd_root, "raw", "notes")

    all_wiki_files = _iter_md_files(pd_root, "wiki")
    # Build a set of "known" files keyed by their relative path fragment
    known_keys: set[str] = set()
    for fpath in all_wiki_files:
        rel = os.path.relpath(fpath, os.path.join(pd_root, "wiki"))
        # Strip .md for matching against wikilink targets
        key = rel[:-3] if rel.endswith(".md") else rel
        known_keys.add(key)

    incoming_links: dict[str, int] = defaultdict(int)
    broken_backlinks: list[dict[str, str]] = []

    # Scan wiki/ AND raw/ for outgoing wikilinks
    scan_dirs = ["wiki", "raw/notes", "raw/source"]
    for scan_dir in scan_dirs:
        for fpath in _iter_md_files(pd_root, scan_dir):
            text = _read_full_text(fpath)
            rel_source = os.path.relpath(fpath, pd_root)
            for raw_target in _extract_wikilinks(text):
                normalised = _normalise_link_target(raw_target)
                incoming_links[normalised] += 1
                # Check if target exists (only for wiki-internal links)
                if normalised.startswith(("concepts/", "methods/", "papers/", "topics/")):
                    target_key = normalised
                    if target_key not in known_keys:
                        broken_backlinks.append({
                            "source": rel_source,
                            "target": raw_target,
                        })

    # Orphaned wiki articles (0 incoming links)
    orphaned: list[str] = []
    for fpath in all_wiki_files:
        rel = os.path.relpath(fpath, os.path.join(pd_root, "wiki"))
        key = rel[:-3] if rel.endswith(".md") else rel
        if incoming_links.get(key, 0) == 0:
            orphaned.append(f"wiki/{rel}")

    results["orphaned_articles"] = {"count": len(orphaned), "items": orphaned}
    results["broken_backlinks"] = {"count": len(broken_backlinks), "items": broken_backlinks}

    # --- Missing frontmatter ------------------------------------------------
    missing_fm: list[dict[str, Any]] = []
    section_dir_map = {
        "inbox": "inbox",
        "raw_source": "raw/source",
        "raw_notes": "raw/notes",
        "papers": "wiki/papers",
        "concepts": "wiki/concepts",
        "methods": "wiki/methods",
        "topics": "wiki/topics",
    }
    for section, rel_dir in section_dir_map.items():
        required = _REQUIRED_FIELDS.get(section, [])
        if not required:
            continue
        for fpath in _iter_md_files(pd_root, rel_dir):
            fm = _parse_frontmatter(fpath)
            missing = [f for f in required if not fm or f not in fm]
            if missing:
                missing_fm.append({
                    "file": os.path.relpath(fpath, pd_root),
                    "missing_fields": missing,
                })
    results["missing_frontmatter"] = {"count": len(missing_fm), "items": missing_fm}

    # --- Stale indexes ------------------------------------------------------
    index_dirs = [
        "", "inbox", "raw", "raw/source", "raw/notes",
        "wiki", "wiki/papers", "wiki/concepts", "wiki/methods", "wiki/topics",
        "queries", "daily-log",
    ]
    stale_indexes: list[dict[str, Any]] = []
    for rel_dir in index_dirs:
        idx_path = os.path.join(pd_root, rel_dir, "_index.md") if rel_dir else os.path.join(pd_root, "_index.md")
        if not os.path.isfile(idx_path):
            stale_indexes.append({"index": os.path.relpath(idx_path, pd_root), "reason": "missing"})

    results["stale_indexes"] = {"count": len(stale_indexes), "items": stale_indexes}

    # --- Uncompiled papers --------------------------------------------------
    raw_notes_data = query_vault_sync(vault_path, section="raw_notes", uncompiled_only=True)
    uncompiled = [
        {"file": item.get("_path", ""), "title": item.get("title", "")}
        for item in raw_notes_data.get("sections", {}).get("raw_notes", [])
    ]
    results["uncompiled_papers"] = {"count": len(uncompiled), "items": uncompiled}

    # --- Missing concept stubs ----------------------------------------------
    # Collect all [[concepts/X]] from wiki/papers/ files
    referenced_concepts: set[str] = set()
    for fpath in _iter_md_files(pd_root, "wiki/papers"):
        text = _read_full_text(fpath)
        for target in _extract_wikilinks(text):
            norm = _normalise_link_target(target)
            if norm.startswith("concepts/"):
                referenced_concepts.add(norm)

    missing_concepts: list[str] = []
    for concept_key in referenced_concepts:
        if concept_key not in known_keys:
            missing_concepts.append(concept_key)

    results["missing_concept_stubs"] = {"count": len(missing_concepts), "items": sorted(missing_concepts)}

    # --- Overall health -----------------------------------------------------
    total_issues = sum(v["count"] for v in results.values() if isinstance(v, dict) and "count" in v)
    if total_issues == 0:
        health = "good"
    elif total_issues <= 5:
        health = "needs_attention"
    else:
        health = "poor"
    results["overall_health"] = health
    results["total_issues"] = total_issues

    return results


# ---------------------------------------------------------------------------
# 2. vault_stats
# ---------------------------------------------------------------------------

def vault_stats_sync(vault_path: str) -> dict[str, Any]:
    """Compute vault statistics from frontmatter metadata."""
    pd_root = os.path.join(vault_path, _PD_ROOT)
    if not os.path.isdir(pd_root):
        return {"error": f"Paper Distill root not found at {pd_root}"}

    # Reuse query_vault_sync for section counts
    all_data = query_vault_sync(vault_path, section="all")
    sections = all_data.get("sections", {})

    # Inbox breakdown by status
    inbox_items = sections.get("inbox", [])
    inbox_by_status: dict[str, int] = Counter()
    for item in inbox_items:
        status = str(item.get("status", "unknown")).lower()
        inbox_by_status[status] += 1

    # Raw counts
    raw_source_count = len(sections.get("raw_source", []))
    raw_notes_items = sections.get("raw_notes", [])
    raw_notes_count = len(raw_notes_items)
    compiled_count = sum(1 for item in raw_notes_items if item.get("compiled") is True)

    # Wiki counts
    papers_count = len(sections.get("papers", []))
    concepts_count = len(sections.get("concepts", []))
    methods_count = len(sections.get("methods", []))
    topics_count = len(sections.get("topics", []))

    # Per-topic paper counts (from raw_notes + papers)
    topic_counts: dict[str, int] = Counter()
    for item in raw_notes_items + sections.get("papers", []):
        topics = item.get("topics", item.get("matched_topics", []))
        if isinstance(topics, str):
            topics = [topics]
        for t in topics:
            topic_counts[t] += 1

    # Daily log and query counts
    daily_logs = len(_iter_md_files(pd_root, "daily-log"))
    queries = len(_iter_md_files(pd_root, "queries"))

    # Most recent file modification across vault
    latest_mtime = 0.0
    for scan_dir in ["inbox", "raw", "wiki", "daily-log", "queries"]:
        for fpath in _iter_md_files(pd_root, scan_dir):
            try:
                mt = os.path.getmtime(fpath)
                if mt > latest_mtime:
                    latest_mtime = mt
            except OSError:
                pass

    last_activity = (
        datetime.fromtimestamp(latest_mtime).isoformat()
        if latest_mtime > 0
        else "never"
    )

    return {
        "inbox": {
            "total": len(inbox_items),
            "by_status": dict(inbox_by_status),
        },
        "raw_source": raw_source_count,
        "raw_notes": raw_notes_count,
        "compiled": compiled_count,
        "compilation_rate": (
            round(compiled_count / raw_notes_count, 2)
            if raw_notes_count > 0
            else 0
        ),
        "wiki": {
            "papers": papers_count,
            "concepts": concepts_count,
            "methods": methods_count,
            "topics": topics_count,
        },
        "by_topic": dict(topic_counts),
        "daily_logs": daily_logs,
        "queries": queries,
        "last_activity": last_activity,
    }


# ---------------------------------------------------------------------------
# 3. analyze_knowledge_graph
# ---------------------------------------------------------------------------

def analyze_knowledge_graph_sync(
    vault_path: str,
    user_topics: list[str] | None = None,
) -> dict[str, Any]:
    """Lightweight graph analysis to find structural gaps in the knowledge base.

    Uses dict/set operations instead of NetworkX.  Returns condensed gap lists
    that an LLM can turn into qualitative research ideas.
    """
    pd_root = os.path.join(vault_path, _PD_ROOT)
    if not os.path.isdir(pd_root):
        return {"error": f"Paper Distill root not found at {pd_root}"}

    # --- Build concept ↔ paper bipartite graph from wiki/ -------------------
    concept_to_papers: dict[str, set[str]] = defaultdict(set)
    paper_to_concepts: dict[str, set[str]] = defaultdict(set)
    paper_meta: dict[str, dict[str, Any]] = {}
    concept_meta: dict[str, dict[str, Any]] = {}

    # Parse wiki/papers for concept references
    for fpath in _iter_md_files(pd_root, "wiki/papers"):
        fm = _parse_frontmatter(fpath)
        if not fm:
            continue
        citekey = fm.get("citekey", os.path.basename(fpath).replace(".md", ""))
        paper_meta[citekey] = {
            "title": fm.get("title", ""),
            "year": fm.get("year"),
            "topics": fm.get("topics", []),
            "limitations": fm.get("limitations", []),
            "open_questions": fm.get("open_questions", []),
        }
        # From frontmatter concepts list
        for c in fm.get("concepts", []):
            concept_to_papers[c].add(citekey)
            paper_to_concepts[citekey].add(c)
        # From wikilinks in body
        text = _read_full_text(fpath)
        for target in _extract_wikilinks(text):
            norm = _normalise_link_target(target)
            if norm.startswith("concepts/"):
                concept_name = norm.split("/", 1)[1]
                concept_to_papers[concept_name].add(citekey)
                paper_to_concepts[citekey].add(concept_name)

    # Parse wiki/concepts for related_concepts
    for fpath in _iter_md_files(pd_root, "wiki/concepts"):
        fm = _parse_frontmatter(fpath)
        if not fm:
            continue
        name = fm.get("concept", os.path.basename(fpath).replace(".md", ""))
        concept_meta[name] = {
            "paper_count": fm.get("paper_count", len(concept_to_papers.get(name, set()))),
            "aliases": fm.get("aliases", []),
            "topics": fm.get("topics", []),
        }

    user_topics_set = set(user_topics or [])

    gaps: dict[str, list[dict[str, Any]]] = {
        "methodology_mismatches": [],
        "combination_opportunities": [],
        "recurring_problems": [],
        "scaling_questions": [],
    }

    # --- Type 2: Methodology Mismatches ------------------------------------
    # Concepts with high paper_count but no overlap with user's primary topics
    if user_topics_set:
        for concept, papers in concept_to_papers.items():
            if len(papers) < 2:
                continue
            paper_topics: set[str] = set()
            for pk in papers:
                meta = paper_meta.get(pk, {})
                topics = meta.get("topics", [])
                if isinstance(topics, str):
                    topics = [topics]
                paper_topics.update(topics)
            if not paper_topics & user_topics_set:
                gaps["methodology_mismatches"].append({
                    "concept": concept,
                    "paper_count": len(papers),
                    "papers": sorted(papers)[:5],
                    "concept_topics": sorted(paper_topics),
                    "reason": f"Proven in {sorted(paper_topics)} but not yet applied to {sorted(user_topics_set)}",
                })

    # --- Type 4: Combination Opportunities ----------------------------------
    # Find concept pairs that share a topic but have no joint paper.
    # Topics can come from concept_meta or from the papers that reference them.
    def _topics_for_concept(name: str) -> set[str]:
        topics: set[str] = set()
        # From concept article frontmatter
        cm = concept_meta.get(name, {})
        for t in cm.get("topics", []):
            topics.add(t)
        # From the papers that reference this concept
        for pk in concept_to_papers.get(name, set()):
            pm = paper_meta.get(pk, {})
            pt = pm.get("topics", [])
            if isinstance(pt, str):
                pt = [pt]
            topics.update(pt)
        return topics

    concept_list = sorted(concept_to_papers.keys())
    for i, c1 in enumerate(concept_list):
        for c2 in concept_list[i + 1:]:
            papers_c1 = concept_to_papers[c1]
            papers_c2 = concept_to_papers[c2]
            # They must each have papers but no shared paper
            if papers_c1 and papers_c2 and not (papers_c1 & papers_c2):
                topics_c1 = _topics_for_concept(c1)
                topics_c2 = _topics_for_concept(c2)
                shared = topics_c1 & topics_c2
                if shared:
                    gaps["combination_opportunities"].append({
                        "concept_pair": [c1, c2],
                        "shared_topics": sorted(shared),
                        "papers_c1": sorted(papers_c1)[:3],
                        "papers_c2": sorted(papers_c2)[:3],
                        "reason": f"Both in {sorted(shared)} but never combined in one paper",
                    })

    # --- Type 1 & 5: Recurring problems and scaling questions ---------------
    # Count keywords in limitations and open_questions across papers
    limitation_keywords: Counter[str] = Counter()
    scaling_signals: list[dict[str, Any]] = []
    scaling_terms = {"limited to", "only tested", "future work", "scale", "sim-to-real", "small-scale", "toy"}

    for citekey, meta in paper_meta.items():
        limitations = meta.get("limitations", [])
        if isinstance(limitations, str):
            limitations = [limitations]
        for lim in limitations:
            lim_lower = lim.lower()
            # Check for scaling signals
            if any(term in lim_lower for term in scaling_terms):
                scaling_signals.append({"paper": citekey, "limitation": lim})
            # Extract noun-phrase keywords (simple: split on common delimiters)
            for word in re.split(r"[,;.\-/]", lim):
                word = word.strip().lower()
                if len(word) > 3:
                    limitation_keywords[word] += 1

        open_qs = meta.get("open_questions", [])
        if isinstance(open_qs, str):
            open_qs = [open_qs]
        for oq in open_qs:
            oq_lower = oq.lower()
            if any(term in oq_lower for term in scaling_terms):
                scaling_signals.append({"paper": citekey, "open_question": oq})

    # Recurring = mentioned in 2+ papers
    for phrase, count in limitation_keywords.most_common(20):
        if count >= 2:
            gaps["recurring_problems"].append({
                "keyword": phrase,
                "occurrence_count": count,
            })

    gaps["scaling_questions"] = scaling_signals[:10]

    # Limit combination_opportunities to top 10
    gaps["combination_opportunities"] = gaps["combination_opportunities"][:10]

    return {
        "paper_count": len(paper_meta),
        "concept_count": len(concept_to_papers),
        "gaps": gaps,
        "gap_summary": {
            "methodology_mismatches": len(gaps["methodology_mismatches"]),
            "combination_opportunities": len(gaps["combination_opportunities"]),
            "recurring_problems": len(gaps["recurring_problems"]),
            "scaling_questions": len(gaps["scaling_questions"]),
        },
    }
