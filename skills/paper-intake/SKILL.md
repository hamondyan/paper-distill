---
name: paper-intake
description: Use when the user wants to discover papers, run a daily digest, summarize a single paper, ingest approved papers, directly add a DOI/arXiv/URL, process inbox approvals, or hand already-ingested papers to Zotero.
---

# Paper Intake

## Overview

Move papers from discovery to approved evidence without bypassing the human approval boundary. The visible path is `inbox -> sources/evidence -> wiki/papers`, with Zotero as an optional handoff.

## Route

- **Quick paper summary:** resolve DOI/arXiv/URL with `resolve_metadata` or `fetch_pdf_text`; summarize motivation, approach, findings, strengths, limitations, and relevance to `settings.json -> paper_distill.research_profile.direction`; offer ingest, compile, or related search as follow-up.
- **Ad-hoc discovery:** read `research_profile`, `topics`, and `scoring`; call `source-discover(..., save_to_inbox=true)`; show best candidates and tell the user to approve or reject inbox cards in Obsidian.
- **Daily digest:** discover across configured topics, use `query-library` to deduplicate against inbox/evidence/papers, write a digest under `insights/digests/`, and keep it as a review workflow rather than auto-ingest.
- **Approved inbox ingest:** call `query-library(section="inbox", status="approved")`; if items exist, call `source-ingest(mode="approved_inbox", status="approved", limit=...)`.
- **Direct add:** for user-confirmed DOI/arXiv/URL, call `source-ingest(mode="direct_identifier", identifier=..., topic_keys=..., collection_name=...)`; do not stage inbox review unless explicitly requested.
- **Zotero collect:** for already-ingested papers, resolve from `wiki/papers` or `sources/evidence`, call `zotero_add`, and report duplicates or configuration warnings.

## Ingest Rules

- Never move `proposed`, `rejected`, or `deferred` inbox notes into `sources/`.
- Capture must write `sources/evidence/{date}/{citekey}.md` before Zotero handoff.
- Canonical paper pages live in `wiki/papers/`.
- If capture or Zotero fails, preserve evidence that was successfully written and report the warning clearly.
- Report source evidence path, wiki paper path, Zotero status, capture fidelity, and whether `/compile` is a useful next step.
