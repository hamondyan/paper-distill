---
name: paper-intake
description: Use when the user wants to discover papers, run a daily digest, summarize a single paper, ingest approved papers, directly add a DOI/arXiv/URL, process inbox approvals, or hand already-ingested papers to Zotero.
---

# Paper Intake

## Overview

Move papers from discovery to approved evidence without bypassing the human approval boundary. The visible path is `inbox -> sources/evidence -> wiki/papers`, with Zotero as an optional handoff.

## Routing Decision

Execute this decision tree **before** any tool call:

1. **User provided a DOI, arXiv ID, or URL?**
   - Yes → Direct Add path: `source-ingest(mode="direct_identifier", identifier=...)`
   - No → Discovery path

2. **Discovery path breakdown:**
   - User gave keywords/topic → `source-discover(query=..., save_to_inbox=true)`
   - No keywords → `source-discover(topic_keys=<from settings>, save_to_inbox=true)`
   - After discovery **stop**: tell the user to approve inbox cards in Obsidian before ingesting

3. **Daily digest path:**
   - Run `source-discover` across all `topic_keys`, then `query-library` to deduplicate
   - Write summary to `insights/digests/`; **never auto-ingest**

4. **Quick summary path (user wants to "read" a paper):**
   - Call `resolve_metadata` or `fetch_pdf_text`; read only, do not write to inbox

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
- Before calling `source-ingest(mode="approved_inbox")`, first call `query-library(section="inbox", status="approved")` to confirm approved items exist. The tool itself does **not** validate `status` — that check is the caller's responsibility.
- On capture failure (`failure_policy: return_to_inbox`): preserve already-written files and report in structured form: `{ success: bool, written_files: [...], errors: [...] }`.

## Skill / Tool Contract

**This Skill is responsible (prompt layer):**
- Parse user intent and route to the correct tool and mode
- Enforce editorial rules (approval gate, status checks)
- Merge content before calling write tools
- Present results in readable form and suggest follow-up actions

**MCP Tool is responsible (Python layer):**
- Perform deterministic I/O (vault read/write, API calls)
- Validate schema and path safety
- Update machine state (compile_state, concept_registry, maintenance_queue)
- Report facts and errors; never make editorial decisions

**Neither layer does:**
- Tools do not judge whether a paper is "good enough" — that is the human inbox decision
- This Skill does not write files directly — all file writes go through tools
- Tools do not read user intent — they only execute the parameters they receive
