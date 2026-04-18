# Frontmatter Reference

YAML frontmatter is intentionally small. Body content carries the research prose; frontmatter carries routing and lookup metadata.

## Inbox Stub

Written by `discover_papers` under `inbox/`.

| Field | Type | Description |
|-------|------|-------------|
| `type` | string | `inbox_stub`. |
| `paper_id` | string | Stable source identifier. |
| `title` | string | Paper title. |
| `source_url` | string | Canonical source URL when available. |
| `discovered_at` | date | Discovery date. |
| `score` | number | Rounded discovery score. |

Approval is not a frontmatter field. Only a plain `#approved` tag in the note body counts.

## Raw Evidence

Written by `ingest_and_read` under `raw/evidence/`.

| Field | Type | Description |
|-------|------|-------------|
| `type` | string | `raw_evidence`. |
| `paper_id` | string | Stable paper ID. |
| `title` | string | Captured title. |
| `source_url` | string | Capture source. |
| `captured_at` | datetime | Capture timestamp. |
| `content_hash` | string | SHA-256 hash of captured Markdown. |

Raw evidence is normally read-only after capture. Capture repair may rewrite the same paper ID.

## Paper Page

Written through `upsert_wiki_page(page_type="paper", ...)` under `wiki/papers/`.
All fields below are required for generated paper pages.

| Field | Type | Description |
|-------|------|-------------|
| `type` | string | Forced to `paper`. |
| `paper_id` | string | Stable paper ID. |
| `title` | string | Paper title. |
| `year` | number | Publication year. |
| `venue` | string | Venue name. |
| `source_layer` | string | Non-empty provenance label; agent-authored canonical pages usually use `wiki`. |
| `key_concepts_topk` | list | One to five most important linked concepts. |

Paper pages are agent-owned and generally not manually edited. Write-time validation rejects missing or empty `paper_id`, `title`, `venue`, or `source_layer`, non-integer `year`, duplicate concepts, or `key_concepts_topk` lists outside the 1-to-5 range. Each paper page must link at least one concept from `key_concepts_topk` in the body with a wikilink such as `[[Transformer]]`. The preferred budget is one to three concept links; more than five concept links is treated as too dense by vault lint. Vault lint also reports `paper_without_raw_evidence` when a paper page has no matching `raw/evidence/` file.

## Concept Page

Written through `upsert_wiki_page(page_type="concept", ...)` under `wiki/concepts/`.
All fields below are required for generated concept pages.

| Field | Type | Description |
|-------|------|-------------|
| `type` | string | Forced to `concept`. |
| `concept` | string | Canonical display name. |
| `aliases` | list | Accepted alternate surfaces. |
| `source_layer` | string | Non-empty provenance label; agent-authored concept pages usually use `wiki`. |
| `related_papers_topk` | list | At least one paper that supports the concept. |

Only core concepts get concept pages. Write-time validation rejects missing or empty `concept` / `source_layer`, non-list `aliases`, or empty `related_papers_topk`. Reuse existing concepts before creating new pages: search with QMD, call `check_concept_alias` when the surface is uncertain, and create a new concept only when it represents a durable research concept supported by at least one paper.

## Idea Page

Written through `upsert_wiki_page(page_type="idea", ...)` under `insights/ideas/`.

| Field | Type | Description |
|-------|------|-------------|
| `type` | string | Forced to `idea`. |
| `idea_state` | string | `active`, `parked`, `rejected`, or `superseded`. |
| `topics` | list | Related topic labels. |
| `related_papers` | list | Supporting paper IDs or paths. |
| `related_concepts` | list | Supporting concept names. |
| `decision_reason` | string | Reason for parking, rejecting, or superseding. |
| `decision_at` | datetime | Decision timestamp. |
| `superseded_by` | string | Stronger idea target when relevant. |

Negative knowledge stays in the idea note itself.

## Conversation Page

Written through `upsert_wiki_page(page_type="conversation", ...)` or the Python conversation insight writer under `insights/conversations/`.

| Field | Type | Description |
|-------|------|-------------|
| `type` | string | Forced to `conversation`. |
| `source_layer` | string | Usually `insights`. |
| `source_thread` | string | Optional originating thread ID. |
| `related_concepts_topk` | list | Up to three related concepts. |
| `captured_at` | datetime | Capture timestamp. |

Conversation pages are distilled insights, not verbatim transcripts.
