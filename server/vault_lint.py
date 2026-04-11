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
from itertools import combinations
from typing import Any

from server.vault_contract import PAPER_DISTILL_ROOT, root_rel_path
from server.vault_query import _parse_frontmatter, query_vault_sync

LOG = logging.getLogger(__name__)

_WIKILINK_RE = re.compile(r"\[\[([^\]|]+)(?:\|[^\]]+)?\]\]")

# Required frontmatter fields per vault section.
_REQUIRED_FIELDS: dict[str, list[str]] = {
    "inbox": ["paper_id", "status"],
    "source_evidence": ["paper_id", "compiled"],
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
    pd_root = os.path.join(vault_path, PAPER_DISTILL_ROOT)
    if not os.path.isdir(pd_root):
        return {"error": f"Paper Distill root not found at {pd_root}"}

    results: dict[str, Any] = {}

    # --- Broken backlinks & orphan analysis ---------------------------------
    # Build two maps:
    #   file_key  → set of outgoing link targets
    #   link_target → set of files that link to it
    wiki_dir = os.path.join(pd_root, "wiki")
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

    # Scan wiki/ and source-layer notes/evidence for outgoing wikilinks
    scan_dirs = ["wiki", root_rel_path("sources_evidence")]
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
        "source_evidence": root_rel_path("sources_evidence"),
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
        "", "inbox", "sources", "sources/evidence",
        "wiki", "wiki/papers", "wiki/concepts", "wiki/methods", "wiki/topics",
        "insights", "insights/queries", "insights/ideas", "insights/dialogues",
        "insights/digests", "memory",
    ]
    stale_indexes: list[dict[str, Any]] = []
    for rel_dir in index_dirs:
        idx_path = os.path.join(pd_root, rel_dir, "_index.md") if rel_dir else os.path.join(pd_root, "_index.md")
        if not os.path.isfile(idx_path):
            stale_indexes.append({"index": os.path.relpath(idx_path, pd_root), "reason": "missing"})

    results["stale_indexes"] = {"count": len(stale_indexes), "items": stale_indexes}

    # --- Uncompiled papers --------------------------------------------------
    uncompiled_data = query_vault_sync(vault_path, section="source_evidence", uncompiled_only=True, detail="full")
    uncompiled = [
        {"file": item.get("_path", ""), "title": item.get("title", "")}
        for item in uncompiled_data.get("sections", {}).get("source_evidence", [])
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

    # --- Semantic duplicate suggestions (4.1) --------------------------------
    _dedup_threshold = 0.75
    _dedup_data = query_vault_sync(vault_path, section="all", detail="full")
    _dedup_sections = _dedup_data.get("sections", {})
    all_papers = list(_dedup_sections.get("source_evidence", [])) + list(_dedup_sections.get("papers", []))
    title_entries: list[tuple[str, str, set[str], str, str]] = []  # (path, title, tokens, paper_id, citekey)
    for item in all_papers:
        title = str(item.get("title", "")).strip()
        path = str(item.get("_path", ""))
        paper_id = str(item.get("paper_id", "")).strip().lower()
        citekey = str(item.get("citekey", "")).strip().lower()
        if title:
            tokens = set(re.sub(r"[^a-z0-9 ]", "", title.lower()).split())
            if tokens:
                title_entries.append((path, title, tokens, paper_id, citekey))

    merge_candidates: list[dict[str, str]] = []
    seen_pairs: set[tuple[str, str]] = set()
    for i, (path_a, title_a, tokens_a, paper_id_a, citekey_a) in enumerate(title_entries):
        for j in range(i + 1, len(title_entries)):
            path_b, title_b, tokens_b, paper_id_b, citekey_b = title_entries[j]
            pair_key = tuple(sorted([path_a, path_b]))
            if pair_key in seen_pairs:
                continue
            if paper_id_a and paper_id_a == paper_id_b:
                continue
            if citekey_a and citekey_a == citekey_b:
                continue
            intersection = len(tokens_a & tokens_b)
            union = len(tokens_a | tokens_b)
            if union > 0 and intersection / union >= _dedup_threshold:
                merge_candidates.append({
                    "file_a": path_a,
                    "title_a": title_a,
                    "file_b": path_b,
                    "title_b": title_b,
                    "similarity": round(intersection / union, 3),
                })
                seen_pairs.add(pair_key)

    results["semantic_duplicates"] = {
        "count": len(merge_candidates),
        "items": merge_candidates[:20],  # cap output
    }

    # --- Registry consistency check (pure read) ----------------------------
    registry_unregistered: list[str] = []
    try:
        from server.database import get_db
        from server.concept_registry import slugify
        conn = get_db(vault_path)
        for fpath in _iter_md_files(pd_root, "wiki/concepts"):
            fm = _parse_frontmatter(fpath)
            if not fm:
                continue
            name = fm.get("concept", os.path.basename(fpath).replace(".md", ""))
            slug = slugify(name)
            row = conn.execute(
                "SELECT id FROM concept_registry WHERE id = ?", (slug,)
            ).fetchone()
            if not row:
                registry_unregistered.append(f"wiki/concepts/{os.path.basename(fpath)}")
    except Exception as exc:
        # DB not yet initialised — skip in a non-breaking way
        LOG.debug("Registry consistency check skipped: %s", exc)

    results["registry_unregistered"] = {
        "count": len(registry_unregistered),
        "items": registry_unregistered,
    }

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
    pd_root = os.path.join(vault_path, PAPER_DISTILL_ROOT)
    if not os.path.isdir(pd_root):
        return {"error": f"Paper Distill root not found at {pd_root}"}

    # Reuse query_vault_sync for section counts
    all_data = query_vault_sync(vault_path, section="all", detail="full")
    sections = all_data.get("sections", {})

    # Inbox breakdown by status
    inbox_items = sections.get("inbox", [])
    inbox_by_status: dict[str, int] = Counter()
    for item in inbox_items:
        status = str(item.get("status", "unknown")).lower()
        inbox_by_status[status] += 1

    # Raw counts
    source_evidence_items = sections.get("source_evidence", [])
    source_evidence_count = len(source_evidence_items)
    compiled_count = sum(1 for item in source_evidence_items if item.get("compiled") is True)

    # Wiki counts
    papers_count = len(sections.get("papers", []))
    concepts_count = len(sections.get("concepts", []))
    methods_count = len(sections.get("methods", []))
    topics_count = len(sections.get("topics", []))

    # Per-topic paper counts (from source evidence + canonical paper pages)
    topic_counts: dict[str, int] = Counter()
    for item in source_evidence_items + sections.get("papers", []):
        topics = item.get("topics", item.get("matched_topics", []))
        if isinstance(topics, str):
            topics = [topics]
        for t in topics:
            topic_counts[t] += 1

    # Daily log and query counts
    daily_logs = len(_iter_md_files(pd_root, root_rel_path("digests")))
    queries = len(_iter_md_files(pd_root, root_rel_path("queries")))

    # Most recent file modification across vault
    latest_mtime = 0.0
    for scan_dir in ["inbox", "sources", "wiki", "insights", "memory"]:
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
        "source_evidence": source_evidence_count,
        "compiled_source_evidence": compiled_count,
        "compilation_rate": (
            round(compiled_count / source_evidence_count, 2)
            if source_evidence_count > 0
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
        "promotion_candidates": _compute_promotion_candidates(
            sections, topic_counts, threshold=5
        ),
        "stale_topics": _compute_stale_topics(
            sections, vault_path, staleness_days=180, new_paper_threshold=3
        ),
    }


# ---------------------------------------------------------------------------
# 2b. Promotion candidates & stale topics helpers
# ---------------------------------------------------------------------------


def _compute_promotion_candidates(
    sections: dict[str, list],
    topic_counts: dict[str, int],
    threshold: int = 5,
) -> list[dict[str, Any]]:
    """Find concepts referenced by ≥threshold papers that aren't yet topics."""
    existing_topics: set[str] = set()
    for topic in sections.get("topics", []):
        for candidate in (
            str(topic.get("title", "")).strip().lower(),
            str(topic.get("topic", "")).strip().lower(),
        ):
            if candidate:
                existing_topics.add(candidate)
        topic_path = str(topic.get("_path", "")).strip()
        if topic_path:
            existing_topics.add(os.path.splitext(os.path.basename(topic_path))[0].lower())

    # Count concept references across compiled wiki papers.
    # query_vault returns frontmatter, not article bodies, so the canonical
    # source here is the `concepts` frontmatter field.
    concept_refs: dict[str, int] = Counter()
    for item in sections.get("papers", []):
        concepts = item.get("concepts", [])
        if isinstance(concepts, str):
            concepts = [concepts]
        for concept in concepts:
            normalized = str(concept).strip().lower()
            if normalized:
                concept_refs[normalized] += 1

    candidates = []
    for name, count in concept_refs.items():
        if count >= threshold and name not in existing_topics:
            candidates.append({
                "concept": name,
                "paper_count": count,
                "suggestion": f"Consider promoting '{name}' to a dedicated topic — referenced by {count} papers.",
            })

    return sorted(candidates, key=lambda x: -x["paper_count"])[:10]


def _compute_stale_topics(
    sections: dict[str, list],
    vault_path: str,
    staleness_days: int = 180,
    new_paper_threshold: int = 3,
) -> list[dict[str, Any]]:
    """Find topics that may need their overview refreshed."""
    now = datetime.now()
    stale = []

    for topic_item in sections.get("topics", []):
        topic_name = str(topic_item.get("title", "")).strip()
        topic_path = topic_item.get("_path", "")
        if not topic_name:
            continue

        # Get last modification time
        full_path = os.path.join(vault_path, topic_path) if topic_path else ""
        last_updated = None
        if full_path and os.path.exists(full_path):
            try:
                mtime = os.path.getmtime(full_path)
                last_updated = datetime.fromtimestamp(mtime)
            except OSError:
                pass

        # Count new source-evidence notes tagged with this topic
        new_count = 0
        for item in sections.get("source_evidence", []):
            topics = item.get("topics", item.get("matched_topics", []))
            if isinstance(topics, str):
                topics = [topics]
            if topic_name.lower() in [t.lower() for t in topics]:
                # Check if source evidence is newer than topic
                note_date = str(
                    item.get("captured_at")
                    or item.get("retrieved_at")
                    or item.get("updated_at", "")
                )
                if last_updated and note_date:
                    try:
                        if note_date > last_updated.isoformat():
                            new_count += 1
                    except (TypeError, ValueError):
                        pass

        reasons = []
        if new_count >= new_paper_threshold:
            reasons.append(f"{new_count} new papers since last update")
        if last_updated:
            days_since = (now - last_updated).days
            if days_since >= staleness_days and new_count > 0:
                reasons.append(f"Last updated {days_since} days ago with {new_count} new papers")

        if reasons:
            stale.append({
                "topic": topic_name,
                "last_updated": last_updated.isoformat() if last_updated else "unknown",
                "new_paper_count": new_count,
                "reasons": reasons,
            })

    return sorted(stale, key=lambda x: -x["new_paper_count"])


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
    pd_root = os.path.join(vault_path, PAPER_DISTILL_ROOT)
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

    # --- IR tension signals (if .state/ir/ exists) -------------------------
    ir_signals: dict[str, Any] = {}
    try:
        from server.compile_ir import aggregate_tension_signals
        ir_signals = aggregate_tension_signals(vault_path, min_occurrence=2)
        if ir_signals.get("papers_scanned", 0) > 0:
            gaps["ir_recurring_limitations"] = ir_signals.get("recurring_limitations", [])
            gaps["ir_open_question_clusters"] = ir_signals.get("open_question_clusters", [])
            gaps["ir_negative_results"] = ir_signals.get("negative_results", [])
            gaps["ir_failure_modes"] = ir_signals.get("failure_modes", [])
            gaps["ir_transfer_constraints"] = ir_signals.get("transfer_constraints", [])
            gaps["benchmark_evaluation_splits"] = _benchmark_evaluation_splits(
                paper_meta,
                ir_signals.get("benchmark_scopes", []),
            )
            gaps["cross_cluster_bridges"] = _cross_cluster_bridges(
                paper_to_concepts,
                concept_to_papers,
                paper_meta,
            )
            gaps["recurring_limitation_spikes"] = [
                item for item in ir_signals.get("recurring_limitations", [])
                if item.get("count", 0) >= 3
            ]
            gaps["contradiction_candidates"] = _contradiction_candidates(
                paper_meta,
                ir_signals.get("negative_results", []),
                ir_signals.get("claimed_novelties", []),
            )
    except Exception as exc:  # noqa: BLE001
        LOG.debug("IR tension signal aggregation skipped: %s", exc)

    summary: dict[str, int] = {
        "methodology_mismatches": len(gaps["methodology_mismatches"]),
        "combination_opportunities": len(gaps["combination_opportunities"]),
        "recurring_problems": len(gaps["recurring_problems"]),
        "scaling_questions": len(gaps["scaling_questions"]),
    }
    if ir_signals.get("papers_scanned", 0) > 0:
        summary["ir_papers_scanned"] = ir_signals["papers_scanned"]
        summary["ir_recurring_limitations"] = len(gaps.get("ir_recurring_limitations", []))
        summary["ir_open_question_clusters"] = len(gaps.get("ir_open_question_clusters", []))
        summary["cross_cluster_bridges"] = len(gaps.get("cross_cluster_bridges", []))
        summary["benchmark_evaluation_splits"] = len(gaps.get("benchmark_evaluation_splits", []))
        summary["contradiction_candidates"] = len(gaps.get("contradiction_candidates", []))
        summary["recurring_limitation_spikes"] = len(gaps.get("recurring_limitation_spikes", []))

    return {
        "paper_count": len(paper_meta),
        "concept_count": len(concept_to_papers),
        "gaps": gaps,
        "gap_summary": summary,
    }


def _cross_cluster_bridges(
    paper_to_concepts: dict[str, set[str]],
    concept_to_papers: dict[str, set[str]],
    paper_meta: dict[str, dict[str, Any]],
) -> list[dict[str, Any]]:
    candidates: list[dict[str, Any]] = []
    for paper, concepts in paper_to_concepts.items():
        if len(concepts) < 2:
            continue
        for c1, c2 in combinations(sorted(concepts), 2):
            prior_overlap = (concept_to_papers.get(c1, set()) & concept_to_papers.get(c2, set())) - {paper}
            if prior_overlap:
                continue
            candidates.append({
                "paper": paper,
                "concept_pair": [c1, c2],
                "topics": paper_meta.get(paper, {}).get("topics", []),
                "reason": f"{paper} is the first observed bridge between {c1} and {c2}",
            })
    return candidates[:20]


def _benchmark_evaluation_splits(
    paper_meta: dict[str, dict[str, Any]],
    benchmark_scopes: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    by_topic: dict[str, dict[str, list[str]]] = defaultdict(lambda: defaultdict(list))
    for entry in benchmark_scopes:
        paper = entry.get("paper", "")
        claim = str(entry.get("claim", "")).strip()
        if not paper or not claim:
            continue
        topics = paper_meta.get(paper, {}).get("topics", [])
        if isinstance(topics, str):
            topics = [topics]
        for topic in topics:
            by_topic[topic][claim.lower()].append(paper)

    candidates: list[dict[str, Any]] = []
    for topic, scopes in by_topic.items():
        if len(scopes) < 2:
            continue
        candidates.append({
            "topic": topic,
            "benchmark_scopes": [
                {"scope": scope, "papers": sorted(set(papers))[:5]}
                for scope, papers in sorted(scopes.items(), key=lambda item: -len(item[1]))
            ],
            "reason": f"{topic} contains multiple benchmark/evaluation regimes",
        })
    return candidates[:10]


def _contradiction_candidates(
    paper_meta: dict[str, dict[str, Any]],
    negative_results: list[dict[str, Any]],
    claimed_novelties: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    novelty_by_paper = {entry.get("paper", ""): str(entry.get("claim", "")).lower() for entry in claimed_novelties}
    candidates: list[dict[str, Any]] = []

    for neg in negative_results:
        paper = neg.get("paper", "")
        claim = str(neg.get("claim", "")).lower()
        if not paper or not claim:
            continue
        topics = paper_meta.get(paper, {}).get("topics", [])
        if isinstance(topics, str):
            topics = [topics]
        neg_keywords = set(re.findall(r"[a-z]{5,}", claim))
        if not neg_keywords:
            continue

        for other_paper, novelty in novelty_by_paper.items():
            if not novelty or other_paper == paper:
                continue
            other_topics = paper_meta.get(other_paper, {}).get("topics", [])
            if isinstance(other_topics, str):
                other_topics = [other_topics]
            if set(topics) & set(other_topics):
                novelty_keywords = set(re.findall(r"[a-z]{5,}", novelty))
                overlap = sorted(neg_keywords & novelty_keywords)
                if len(overlap) >= 2:
                    candidates.append({
                        "paper": paper,
                        "other_paper": other_paper,
                        "shared_topics": sorted(set(topics) & set(other_topics)),
                        "keyword_overlap": overlap[:6],
                        "reason": f"Negative result in {paper} overlaps novelty claims in {other_paper}",
                    })
    return candidates[:20]
