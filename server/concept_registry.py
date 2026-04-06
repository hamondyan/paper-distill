"""Concept Canonical Registry.

Provides a persistent, canonical mapping for concepts, methods, and topics
used across the Paper Distill knowledge base.  Ensures that the same idea
is always referred to by a single canonical name, with aliases tracked and
merges recorded for traceability.

Auto-merge is limited to three hard-coded cases (slug match, abbreviation
whitelist, spelling variants).  All other merge candidates go through
human confirmation via the maintenance queue.
"""
from __future__ import annotations

import logging
import os
import re
import sqlite3
from typing import Any

from server.database import get_db, _now_iso

LOG = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Slug normalisation
# ---------------------------------------------------------------------------

_NON_ALPHANUM = re.compile(r"[^a-z0-9]+")


def slugify(text: str) -> str:
    """Produce a stable slug from a surface form.

    ``"Vision-Language-Action Models"`` → ``"vision-language-action-models"``
    """
    return _NON_ALPHANUM.sub("-", text.lower().strip()).strip("-")


# ---------------------------------------------------------------------------
# Abbreviation whitelist (hard-coded, expanding requires code change)
# ---------------------------------------------------------------------------

_ABBREVIATION_WHITELIST: dict[str, str] = {
    "vla": "vision-language-action",
    "vlm": "vision-language-model",
    "llm": "large-language-model",
    "llms": "large-language-models",
    "rl": "reinforcement-learning",
    "il": "imitation-learning",
    "bc": "behavioral-cloning",
    "vit": "vision-transformer",
    "cnn": "convolutional-neural-network",
    "gan": "generative-adversarial-network",
    "nerf": "neural-radiance-field",
    "slam": "simultaneous-localization-and-mapping",
    "mpc": "model-predictive-control",
    "ppo": "proximal-policy-optimization",
    "dpo": "direct-preference-optimization",
    "sac": "soft-actor-critic",
    "ddpm": "denoising-diffusion-probabilistic-model",
    "dit": "diffusion-transformer",
    "moe": "mixture-of-experts",
    "lora": "low-rank-adaptation",
    "rag": "retrieval-augmented-generation",
    "rt": "robotics-transformer",
}

# Build reverse map: full-slug → abbreviation-slug
_ABBREVIATION_REVERSE: dict[str, str] = {v: k for k, v in _ABBREVIATION_WHITELIST.items()}


# ---------------------------------------------------------------------------
# Spelling variants (British ↔ American, etc.)
# ---------------------------------------------------------------------------

_SPELLING_VARIANTS: list[tuple[str, str]] = [
    ("behavior", "behaviour"),
    ("modeling", "modelling"),
    ("optimization", "optimisation"),
    ("color", "colour"),
    ("center", "centre"),
    ("analyze", "analyse"),
    ("normalize", "normalise"),
    ("generalize", "generalise"),
    ("minimize", "minimise"),
    ("maximize", "maximise"),
    ("recognize", "recognise"),
    ("tokenize", "tokenise"),
    ("parameterize", "parameterise"),
    ("vectorize", "vectorise"),
    ("categorize", "categorise"),
    ("fiber", "fibre"),
    ("defense", "defence"),
    ("offense", "offence"),
    ("license", "licence"),
    ("labeled", "labelled"),
    ("traveled", "travelled"),
    ("canceled", "cancelled"),
]


def _spelling_equivalent(slug_a: str, slug_b: str) -> bool:
    """Return True if *slug_a* and *slug_b* differ only by a known
    British/American spelling variant."""
    if slug_a == slug_b:
        return True
    for us, uk in _SPELLING_VARIANTS:
        if slug_a.replace(us, uk) == slug_b or slug_b.replace(us, uk) == slug_a:
            return True
        if slug_a.replace(uk, us) == slug_b or slug_b.replace(uk, us) == slug_a:
            return True
    return False


# ---------------------------------------------------------------------------
# Auto-merge eligibility (3 hard-coded cases)
# ---------------------------------------------------------------------------

def auto_merge_eligible(surface_a: str, surface_b: str) -> str | None:
    """Determine if two surface forms are auto-mergeable.

    Returns the merge reason string if eligible, or ``None``.
    Only three cases qualify — expanding this list requires a code change,
    not a parameter tweak.
    """
    slug_a = slugify(surface_a)
    slug_b = slugify(surface_b)

    # Case 1: identical slug after normalisation
    if slug_a == slug_b:
        return "slug_match"

    # Case 2: abbreviation ↔ full name in whitelist
    expanded_a = _ABBREVIATION_WHITELIST.get(slug_a)
    expanded_b = _ABBREVIATION_WHITELIST.get(slug_b)
    if expanded_a and expanded_a == slug_b:
        return f"abbreviation_whitelist:{slug_a}={slug_b}"
    if expanded_b and expanded_b == slug_a:
        return f"abbreviation_whitelist:{slug_b}={slug_a}"
    # Also check reverse (full → abbreviation)
    abbrev_a = _ABBREVIATION_REVERSE.get(slug_a)
    abbrev_b = _ABBREVIATION_REVERSE.get(slug_b)
    if abbrev_a and abbrev_a == slug_b:
        return f"abbreviation_whitelist:{slug_a}={slug_b}"
    if abbrev_b and abbrev_b == slug_a:
        return f"abbreviation_whitelist:{slug_b}={slug_a}"

    # Case 3: spelling variant
    if _spelling_equivalent(slug_a, slug_b):
        return "spelling_variant"

    return None


# ---------------------------------------------------------------------------
# Slug candidate expansion
# ---------------------------------------------------------------------------

def _expand_slug_candidates(slug: str) -> list[str]:
    """Return alternative slugs to check for auto-merge when registering.

    Produces up to three candidates:
    - abbreviation → expanded form (e.g. "vla" → "vision-language-action")
    - full form → abbreviation  (e.g. "vision-language-action" → "vla")
    - spelling variant          (e.g. "behavioral-cloning" → "behavioural-cloning")
    """
    candidates: list[str] = []
    expanded = _ABBREVIATION_WHITELIST.get(slug)
    if expanded:
        candidates.append(expanded)
    abbrev = _ABBREVIATION_REVERSE.get(slug)
    if abbrev:
        candidates.append(abbrev)
    for us, uk in _SPELLING_VARIANTS:
        if us in slug:
            candidates.append(slug.replace(us, uk))
        elif uk in slug:
            candidates.append(slug.replace(uk, us))
    return candidates


# ---------------------------------------------------------------------------
# Registry CRUD
# ---------------------------------------------------------------------------


def register_concept(
    vault_path: str,
    canonical: str,
    concept_type: str = "concept",
    aliases: list[str] | None = None,
) -> dict[str, Any]:
    """Register a new concept (or return existing if slug matches).

    Parameters
    ----------
    canonical : str
        The display name (e.g. "Diffusion Policy").
    concept_type : str
        One of "concept", "method", "topic".
    aliases : list[str] | None
        Additional surface forms to register as aliases.

    Returns
    -------
    dict with ``id``, ``canonical``, ``type``, ``created`` (bool),
    ``merged_into`` (str or None if auto-merged into existing).
    """
    conn = get_db(vault_path)
    slug = slugify(canonical)
    now = _now_iso()

    # Check if concept already exists by slug
    existing = conn.execute(
        "SELECT * FROM concept_registry WHERE id = ?", (slug,)
    ).fetchone()

    if existing:
        # Register new aliases if any
        _register_aliases(conn, slug, aliases or [])
        return {
            "id": slug,
            "canonical": existing["canonical"],
            "type": existing["type"],
            "created": False,
            "merged_into": None,
        }

    # Check if any alias points to an existing concept
    all_surface_forms = [canonical] + (aliases or [])
    for form in all_surface_forms:
        resolved = _resolve_by_alias(conn, form)
        if resolved:
            # Auto-merge check
            reason = auto_merge_eligible(canonical, resolved["canonical"])
            if reason:
                _register_aliases(conn, resolved["id"], [canonical] + (aliases or []))
                LOG.info(
                    "Auto-merged '%s' into '%s' (reason: %s)",
                    canonical, resolved["canonical"], reason,
                )
                return {
                    "id": resolved["id"],
                    "canonical": resolved["canonical"],
                    "type": resolved["type"],
                    "created": False,
                    "merged_into": resolved["id"],
                }

    # Check abbreviation expansion against existing registry entries.
    # E.g. registering "VLA" should find existing "vision-language-action".
    for candidate_slug in _expand_slug_candidates(slug):
        existing = conn.execute(
            "SELECT * FROM concept_registry WHERE id = ?", (candidate_slug,)
        ).fetchone()
        if existing:
            reason = auto_merge_eligible(canonical, existing["canonical"])
            if reason:
                _register_aliases(conn, existing["id"], [canonical] + (aliases or []))
                LOG.info(
                    "Auto-merged '%s' into '%s' (reason: %s)",
                    canonical, existing["canonical"], reason,
                )
                return {
                    "id": existing["id"],
                    "canonical": existing["canonical"],
                    "type": existing["type"],
                    "created": False,
                    "merged_into": existing["id"],
                }

    # Create new concept
    conn.execute(
        """INSERT INTO concept_registry
           (id, canonical, type, version, promoted, paper_count, created_at, updated_at)
           VALUES (?, ?, ?, 1, 0, 0, ?, ?)""",
        (slug, canonical, concept_type, now, now),
    )
    # Register the canonical name + aliases
    _register_aliases(conn, slug, [canonical] + (aliases or []))
    conn.commit()

    return {
        "id": slug,
        "canonical": canonical,
        "type": concept_type,
        "created": True,
        "merged_into": None,
    }


def _register_aliases(conn: sqlite3.Connection, concept_id: str, surface_forms: list[str]) -> int:
    """Register surface forms as aliases.  Returns count of newly added."""
    added = 0
    for form in surface_forms:
        normalised = slugify(form)
        if not normalised:
            continue
        try:
            conn.execute(
                "INSERT OR IGNORE INTO concept_aliases (alias, concept_id) VALUES (?, ?)",
                (normalised, concept_id),
            )
            added += 1
        except sqlite3.IntegrityError:
            pass
    conn.commit()
    return added


def _resolve_by_alias(conn: sqlite3.Connection, surface_form: str) -> dict | None:
    """Look up a concept by alias."""
    normalised = slugify(surface_form)
    row = conn.execute(
        """SELECT cr.* FROM concept_aliases ca
           JOIN concept_registry cr ON ca.concept_id = cr.id
           WHERE ca.alias = ?""",
        (normalised,),
    ).fetchone()
    return dict(row) if row else None


def resolve_concept(vault_path: str, surface_form: str) -> dict[str, Any] | None:
    """Resolve a surface form to its canonical concept.

    Tries in order:
    1. Exact alias match (slugified)
    2. Slug match against concept_registry.id
    3. Abbreviation expansion then retry
    """
    conn = get_db(vault_path)
    slug = slugify(surface_form)

    # 1. Alias lookup
    result = _resolve_by_alias(conn, surface_form)
    if result:
        return {
            "id": result["id"],
            "canonical": result["canonical"],
            "type": result["type"],
            "version": result["version"],
        }

    # 2. Direct slug match
    row = conn.execute(
        "SELECT * FROM concept_registry WHERE id = ?", (slug,)
    ).fetchone()
    if row:
        return {
            "id": row["id"],
            "canonical": row["canonical"],
            "type": row["type"],
            "version": row["version"],
        }

    # 3. Try abbreviation expansion
    expanded = _ABBREVIATION_WHITELIST.get(slug)
    if expanded:
        row = conn.execute(
            "SELECT * FROM concept_registry WHERE id = ?", (expanded,)
        ).fetchone()
        if row:
            return {
                "id": row["id"],
                "canonical": row["canonical"],
                "type": row["type"],
                "version": row["version"],
            }

    return None


def merge_concepts(
    vault_path: str,
    from_id: str,
    to_id: str,
    reason: str = "",
) -> dict[str, Any]:
    """Merge concept *from_id* into *to_id*.

    - All aliases of *from_id* are re-mapped to *to_id*.
    - *from_id*'s paper_count is added to *to_id*.
    - *to_id*'s version is incremented.
    - *from_id* is deleted from the registry.
    - The merge is recorded in ``concept_merge_history``.
    """
    conn = get_db(vault_path)
    now = _now_iso()

    from_row = conn.execute(
        "SELECT * FROM concept_registry WHERE id = ?", (from_id,)
    ).fetchone()
    to_row = conn.execute(
        "SELECT * FROM concept_registry WHERE id = ?", (to_id,)
    ).fetchone()

    if not from_row:
        return {"error": f"Source concept '{from_id}' not found"}
    if not to_row:
        return {"error": f"Target concept '{to_id}' not found"}

    # Re-map aliases
    conn.execute(
        "UPDATE concept_aliases SET concept_id = ? WHERE concept_id = ?",
        (to_id, from_id),
    )
    # Also register from_id's slug as alias of to_id
    conn.execute(
        "INSERT OR IGNORE INTO concept_aliases (alias, concept_id) VALUES (?, ?)",
        (from_id, to_id),
    )

    # Update paper count and version
    merged_paper_count = (from_row["paper_count"] or 0) + (to_row["paper_count"] or 0)
    conn.execute(
        """UPDATE concept_registry
           SET paper_count = ?, version = version + 1, updated_at = ?
           WHERE id = ?""",
        (merged_paper_count, now, to_id),
    )

    # Record merge history
    conn.execute(
        """INSERT INTO concept_merge_history
           (from_concept, to_concept, merged_at, reason)
           VALUES (?, ?, ?, ?)""",
        (from_id, to_id, now, reason),
    )

    # Delete source concept
    conn.execute("DELETE FROM concept_registry WHERE id = ?", (from_id,))
    conn.commit()

    LOG.info("Merged concept '%s' into '%s' (reason: %s)", from_id, to_id, reason)

    return {
        "merged": True,
        "from_id": from_id,
        "to_id": to_id,
        "new_version": to_row["version"] + 1,
        "paper_count": merged_paper_count,
    }


def list_concepts(
    vault_path: str,
    concept_type: str | None = None,
    min_paper_count: int = 0,
) -> list[dict[str, Any]]:
    """List concepts from the registry, optionally filtered."""
    conn = get_db(vault_path)
    query = "SELECT * FROM concept_registry WHERE 1=1"
    params: list[Any] = []

    if concept_type:
        query += " AND type = ?"
        params.append(concept_type)
    if min_paper_count > 0:
        query += " AND paper_count >= ?"
        params.append(min_paper_count)

    query += " ORDER BY paper_count DESC, canonical ASC"
    rows = conn.execute(query, params).fetchall()
    return [dict(row) for row in rows]


def get_concept(vault_path: str, concept_id: str) -> dict[str, Any] | None:
    """Get a single concept with its aliases."""
    conn = get_db(vault_path)
    row = conn.execute(
        "SELECT * FROM concept_registry WHERE id = ?", (concept_id,)
    ).fetchone()
    if not row:
        return None

    aliases = conn.execute(
        "SELECT alias FROM concept_aliases WHERE concept_id = ?", (concept_id,)
    ).fetchall()

    result = dict(row)
    result["aliases"] = [a["alias"] for a in aliases]
    return result


def update_paper_count(vault_path: str, concept_id: str, delta: int = 1) -> None:
    """Increment the paper_count for a concept."""
    conn = get_db(vault_path)
    conn.execute(
        """UPDATE concept_registry
           SET paper_count = paper_count + ?, updated_at = ?
           WHERE id = ?""",
        (delta, _now_iso(), concept_id),
    )
    conn.commit()


def promote_concept(vault_path: str, concept_id: str) -> dict[str, Any]:
    """Promote a concept to topic type.  Increments version."""
    conn = get_db(vault_path)
    now = _now_iso()
    row = conn.execute(
        "SELECT * FROM concept_registry WHERE id = ?", (concept_id,)
    ).fetchone()
    if not row:
        return {"error": f"Concept '{concept_id}' not found"}

    conn.execute(
        """UPDATE concept_registry
           SET type = 'topic', promoted = 1, version = version + 1, updated_at = ?
           WHERE id = ?""",
        (now, concept_id),
    )
    conn.commit()

    return {
        "promoted": True,
        "id": concept_id,
        "new_type": "topic",
        "new_version": row["version"] + 1,
    }


# ---------------------------------------------------------------------------
# Backfill from existing wiki
# ---------------------------------------------------------------------------

def backfill_registry_from_wiki(vault_path: str) -> dict[str, Any]:
    """Populate the registry from existing wiki/papers and wiki/concepts.

    Does NOT create IR (that requires LLM).  Only backfills:
    - concepts from wiki/concepts/ frontmatter → concept_registry
    - methods from wiki/methods/ frontmatter  → concept_registry (type=method)
    - paper → concept references → compile_deps
    - compile_state entries marked schema_version="legacy"
    """
    from server.vault_query import _parse_frontmatter
    from server.vault_lint import _iter_md_files, _extract_wikilinks, _normalise_link_target

    pd_root = os.path.join(vault_path, "Paper Distill")
    if not os.path.isdir(pd_root):
        return {"error": f"Paper Distill root not found at {pd_root}"}

    conn = get_db(vault_path)
    now = _now_iso()
    stats = {"concepts_registered": 0, "methods_registered": 0, "papers_indexed": 0, "deps_created": 0}

    def _backfill_entity(rel_dir: str, name_key: str, entity_type: str, count_key: str) -> None:
        for fpath in _iter_md_files(pd_root, rel_dir):
            fm = _parse_frontmatter(fpath)
            if not fm:
                continue
            name = fm.get(name_key, os.path.basename(fpath).replace(".md", ""))
            slug = slugify(name)
            if conn.execute("SELECT id FROM concept_registry WHERE id = ?", (slug,)).fetchone():
                continue
            paper_count = fm.get("paper_count", 0)
            aliases_raw = fm.get("aliases", [])
            if isinstance(aliases_raw, str):
                aliases_raw = [aliases_raw]
            conn.execute(
                """INSERT INTO concept_registry
                   (id, canonical, type, version, promoted, paper_count, created_at, updated_at)
                   VALUES (?, ?, ?, 1, 0, ?, ?, ?)""",
                (slug, name, entity_type, paper_count, now, now),
            )
            _register_aliases(conn, slug, [name] + aliases_raw)
            stats[count_key] += 1

    _backfill_entity("wiki/concepts", "concept", "concept", "concepts_registered")
    _backfill_entity("wiki/methods", "method", "method", "methods_registered")

    # 3. Backfill paper → concept dependencies
    for fpath in _iter_md_files(pd_root, "wiki/papers"):
        fm = _parse_frontmatter(fpath)
        if not fm:
            continue
        citekey = fm.get("citekey", os.path.basename(fpath).replace(".md", ""))

        # Register compile_state as legacy
        conn.execute(
            """INSERT OR IGNORE INTO compile_state
               (page_id, page_type, compile_version, schema_version, compiled_at)
               VALUES (?, 'paper', 1, 'legacy', ?)""",
            (citekey, now),
        )
        stats["papers_indexed"] += 1

        # Parse concept references from frontmatter + wikilinks
        concept_refs: set[str] = set()
        for c in fm.get("concepts", []):
            concept_refs.add(slugify(str(c)))

        text = ""
        try:
            with open(fpath, "r", encoding="utf-8") as f:
                text = f.read(32768)
        except (OSError, UnicodeDecodeError):
            pass

        for target in _extract_wikilinks(text):
            norm = _normalise_link_target(target)
            if norm.startswith("concepts/"):
                concept_refs.add(slugify(norm.split("/", 1)[1]))

        for concept_slug in concept_refs:
            if not concept_slug:
                continue
            # Only create dep if concept exists in registry
            reg = conn.execute(
                "SELECT id, version FROM concept_registry WHERE id = ?",
                (concept_slug,),
            ).fetchone()
            if reg:
                conn.execute(
                    """INSERT OR IGNORE INTO compile_deps
                       (page_id, page_type, dep_type, dep_id, dep_version)
                       VALUES (?, 'paper', 'concept', ?, ?)""",
                    (citekey, reg["id"], reg["version"]),
                )
                stats["deps_created"] += 1

    conn.commit()
    return stats


