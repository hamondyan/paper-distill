---
name: using-paper-distill
description: Use at the start of any session involving Paper Distill — when the user mentions "paper distill", "knowledge vault", "my wiki", "my papers", "阅读笔记", "知识库", opens a research session, or asks what Paper Distill can do. Load this skill early so the right sub-skills are invoked for subsequent requests in the session.
---

# Paper Distill — Human-Approved Research Knowledge Base

You are equipped with **Paper Distill**: discover papers, stage for human approval, capture arXiv-backed source material, hand off to Zotero, and compile a structured Obsidian wiki. You are the sole writer of the markdown knowledge base. The user owns the approval boundary.

## Vault Structure

`{vault}/Paper Distill/` with sections: `inbox/` (candidates), `raw/source/` (cleaned arXiv captures), `raw/notes/` (CRGP-DNL reading notes), `zotero/imports/` (local import packs), `wiki/` (papers/concepts/methods/topics), `daily-log/`, `queries/`.

## Research Profile

Guided by `settings.json → paper_distill.research_profile`: direction, whitelist_authors, seed_papers, learned_preferences. Always load before discovery, approval, or compilation.

## Available Skills

| Skill | Purpose |
|-------|---------|
| `paper-discover` | Search and stage candidates in inbox/ |
| `process-inbox` | Full pipeline: approved inbox → raw/source + raw/notes → Zotero |
| `paper-add` | Directly add a user-confirmed paper into raw/ + Zotero |
| `paper-ingest` | Manual direct approval (bypasses inbox) |
| `paper-collect` | Zotero management for already-ingested papers |
| `wiki-compile` | Compile raw/ into wiki articles |
| `daily-digest` | Daily candidate discovery digest |
| `knowledge-query` | Query the approved knowledge base |
| `wiki-lint` | Deterministic wiki health check |
| `idea-generator` | Research gap analysis with graph-based detection |
| `paper-summarize` | Quick paper summary without ingestion |

## Commands

`/discover`, `/search`, `/add-paper`, `/process-inbox`, `/compile`, `/lint`, `/query`, `/ingest`, `/digest`, `/status`, `/ideas`, `/summarize`

## Core Rules

1. **Inbox is the approval boundary.** Discovery writes to inbox/, not raw/.
2. **Only approved papers enter raw.** `raw/source` = evidence; `raw/notes` = CRGP-DNL structured understanding.
3. **Frontmatter is king.** AI reads the vault through structured metadata. Use `query_vault` for reads — **never parse `_index.md`** (Dataview syntax, not data).
4. **CRGP-DNL structure is mandatory** for all reading notes: Context, Related Work, Gap, Proposal, Key Results, Discussion, Next Steps. Keep prose concise and structured — no rambling paragraphs.
5. **Use backlinks.** Every compiled paper → ≥2 concept pages. Concept stubs created only when referenced by ≥2 papers.
6. **User-supplied confirmed papers go straight to `paper-add`.** Do not stage them in inbox unless the user explicitly asks.
7. **When in doubt, invoke the relevant Paper Distill skill.**
