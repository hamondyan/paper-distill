"""Paper normalization helpers shared across search and scoring."""
from __future__ import annotations

import hashlib
import re
from typing import Any


_WORKSHOP_PATTERN = re.compile(
    r"\b(workshop|demo|challenge|tutorial|abstract|poster|workshops)\b",
    re.IGNORECASE,
)


def normalise_title(title: str) -> str:
    t = (title or "").lower().strip().rstrip(".")
    for ch in (":", "-", "(", ")", "[", "]", "'", '"', ",", ";"):
        t = t.replace(ch, " ")
    return " ".join(t.split())


def title_tokens(title: str) -> set[str]:
    return set(normalise_title(title).split())


def first_author_surname(paper: dict[str, Any]) -> str:
    authors = paper.get("authors")
    if not authors:
        return ""
    first = authors[0] if isinstance(authors, list) else str(authors).split(",")[0]
    if isinstance(first, dict):
        first = first.get("family", first.get("name", ""))
    return str(first).strip().split()[-1].lower() if first else ""


def extract_arxiv_id(value: str) -> str:
    if not value:
        return ""
    match = re.search(
        r"(?:arxiv\.org/(?:abs|pdf)/|arxiv:|arxiv\.)(\d{4}\.\d{4,5})(?:v\d+)?",
        value,
        re.IGNORECASE,
    )
    return match.group(1) if match else ""


def paper_arxiv_id(paper: dict[str, Any]) -> str:
    for key in ("arxiv_id", "doi", "open_access_url", "url"):
        value = paper.get(key)
        if not value:
            continue
        arxiv_id = extract_arxiv_id(str(value))
        if arxiv_id:
            return arxiv_id
    return ""


def canonical_pdf_url(paper: dict[str, Any]) -> str:
    arxiv_id = paper_arxiv_id(paper)
    if arxiv_id:
        return f"https://arxiv.org/pdf/{arxiv_id}.pdf"

    for key in ("pdf_url", "open_access_url", "url"):
        value = str(paper.get(key, "")).strip()
        if not value:
            continue
        if value.lower().endswith(".pdf"):
            return value
    return ""


def canonical_html_url(paper: dict[str, Any]) -> str:
    arxiv_id = paper_arxiv_id(paper)
    if arxiv_id:
        return f"https://ar5iv.labs.arxiv.org/html/{arxiv_id}"

    for key in ("html_url", "url"):
        value = str(paper.get(key, "")).strip()
        if value:
            return value
    return ""


def canonical_item_url(paper: dict[str, Any]) -> str:
    html_url = canonical_html_url(paper)
    if html_url:
        return html_url

    doi = str(paper.get("doi", "")).strip()
    if doi:
        return f"https://doi.org/{doi}"

    return str(paper.get("url") or paper.get("open_access_url") or "").strip()


def paper_id(paper: dict[str, Any]) -> str:
    doi = str(paper.get("doi", "")).strip().lower()
    if doi:
        return f"doi:{doi}"

    arxiv_id = paper_arxiv_id(paper)
    if arxiv_id:
        return f"arxiv:{arxiv_id.lower()}"

    title = normalise_title(str(paper.get("title", "")))
    author = first_author_surname(paper)
    year = str(paper.get("year") or "").strip()
    digest = hashlib.sha1(f"{title}|{author}|{year}".encode("utf-8")).hexdigest()[:12]
    return f"hash:{digest}"


def is_workshop_like(venue: str) -> bool:
    return bool(_WORKSHOP_PATTERN.search(venue or ""))


def canonical_venue_map(venue_aliases: dict[str, str] | None = None) -> dict[str, str]:
    aliases = {
        "nips": "NeurIPS",
        "neurips": "NeurIPS",
        "conference on robot learning": "CoRL",
    }
    for key, value in (venue_aliases or {}).items():
        aliases[key.strip().lower()] = value
    return aliases


def normalize_venue(raw_venue: str, venue_aliases: dict[str, str] | None = None) -> str:
    venue = (raw_venue or "").strip()
    if not venue:
        return ""

    aliases = canonical_venue_map(venue_aliases)
    lowered = venue.lower()
    for alias, canonical in aliases.items():
        if alias in lowered:
            return canonical

    if "conference on computer vision and pattern recognition" in lowered:
        return "CVPR"
    if "international conference on computer vision" in lowered:
        return "ICCV"
    if "european conference on computer vision" in lowered:
        return "ECCV"
    if "international conference on machine learning" in lowered:
        return "ICML"
    if "international conference on learning representations" in lowered:
        return "ICLR"
    if "association for the advancement of artificial intelligence" in lowered:
        return "AAAI"
    if "international conference on robotics and automation" in lowered:
        return "ICRA"
    if "international conference on intelligent robots and systems" in lowered:
        return "IROS"
    if "robotics science and systems" in lowered:
        return "RSS"

    if venue.isupper() and len(venue) <= 10:
        return venue
    return venue


def normalize_venue_tier(
    raw_venue: str,
    venue_aliases: dict[str, str] | None = None,
    venue_tiers: dict[str, list[str]] | None = None,
) -> tuple[str, str]:
    normalized = normalize_venue(raw_venue, venue_aliases)
    if not normalized:
        return "", "unknown"

    if is_workshop_like(raw_venue):
        return normalized, "workshop_or_unclear"

    tiers = venue_tiers or {}
    for tier_name, venues in tiers.items():
        if normalized in venues:
            return normalized, tier_name
    return normalized, "unknown"
