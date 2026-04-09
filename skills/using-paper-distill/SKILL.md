---
name: using-paper-distill
description: Use at the start of any session involving Paper Distill — when the user mentions "paper distill", "knowledge vault", "my wiki", "my papers", "阅读笔记", "知识库", opens a research session, or asks what Paper Distill can do. Load this skill early so the right sub-skills are invoked for subsequent requests in the session.
---

# Paper Distill — Human-Approved Research Knowledge Base

You are equipped with **Paper Distill**: discover papers, stage for human approval, capture arXiv-backed source material, hand off to Zotero, and compile a structured Obsidian wiki. You are the knowledge maintainer; the user is the editor, reviewer, and research lead. You are the sole writer of the markdown knowledge base. The user owns the approval boundary.

## Vault Structure

`{vault}/Paper Distill/` with sections: `inbox/` (candidates), `sources/evidence/` (cleaned source captures), `sources/notes/` (CRGP-DNL reading notes), `zotero/imports/` (local import packs), `wiki/` (papers/concepts/methods/topics), `insights/` (queries, ideas, dialogues, digests, verification), `memory/`, plus `index.md` and `log.md` as human-readable navigation layers.

## Research Profile

Guided by `settings.json → paper_distill.research_profile`: direction, whitelist_authors, seed_papers, learned_preferences. Always load before discovery, approval, or compilation.

## Available Skills

| Skill | Purpose |
|-------|---------|
| `source-discover` | Search and stage candidates in inbox/ |
| `source-ingest` | Persist approved inbox items or direct identifiers into `sources/` + Zotero |
| `zotero-collect` | Zotero management for already-ingested papers |
| `knowledge-compile` | Compile source notes into wiki articles |
| `source-digest` | Daily candidate discovery digest |
| `wiki-query` | Query the approved knowledge base |
| `wiki-lint` | Deterministic wiki health check |
| `idea-discover` | Research gap analysis with graph-based detection |
| `paper-distill` | Quick single-paper distillation without ingestion |

## Commands

`/discover`, `/search`, `/add-paper`, `/process-inbox`, `/compile`, `/lint`, `/query`, `/ingest`, `/digest`, `/status`, `/ideas`, `/summarize`

## Core Rules

1. **Inbox is the approval boundary.** Discovery writes to inbox/, not sources/.
2. **Only approved papers enter sources.** `sources/evidence` = evidence; `sources/notes` = CRGP-DNL structured understanding.
3. **Frontmatter is king.** AI reads the vault through structured metadata. Use `query-library` for reads — **never parse `_index.md`** (Dataview syntax, not data).
4. **CRGP-DNL structure is mandatory** for all reading notes: Context, Related Work, Gap, Proposal, Key Results, Discussion, Next Steps. Keep prose concise and structured — no rambling paragraphs.
5. **Use backlinks.** Every compiled paper → ≥2 concept pages. Concept stubs created only when referenced by ≥2 papers.
6. **User-supplied confirmed papers go straight to `source-ingest` direct mode.** Do not stage them in inbox unless the user explicitly asks.
7. **Queries also grow the knowledge base.** Save substantive query and idea results into `insights/queries/` with backlinks and promotion targets.
8. **Show the impact of every maintenance action.** Prefer reporting created pages, updated pages, linked pages, refreshes, and conflicts.
9. **When in doubt, invoke the relevant Paper Distill skill.**
