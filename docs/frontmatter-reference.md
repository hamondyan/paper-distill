# Frontmatter Reference

YAML frontmatter fields for each note type in the Paper Distill vault.

---

## Inbox Note

Written by `source-discover` when `save_to_inbox=true`. Located at `inbox/{date}/{citekey}.md`.

| Field | Type | Values / Example | Description |
|-------|------|-----------------|-------------|
| `type` | string | `"inbox-paper"` | Note type identifier |
| `status` | string | `proposed`, `approved`, `rejected`, `deferred` | Human approval state. Only `approved` is ingested. |
| `paper_id` | string | `"S2:abc123"` | Stable source identifier |
| `doi` | string | `"10.48550/arxiv.2410.24164"` | DOI if available |
| `arxiv_id` | string | `"2410.24164"` | arXiv ID if available |
| `title` | string | | Paper title |
| `authors` | list | `["Author A", "Author B"]` | Author names |
| `year` | int | `2024` | Publication year |
| `venue` | string | `"NeurIPS"` | Normalized venue name |
| `abstract` | string | | Paper abstract |
| `score_total` | float | `0.82` | Composite score (0–1) |
| `score_breakdown` | dict | `{ topic_fit: 0.95, recency: 0.70, ... }` | Per-factor scores |
| `best_topic` | string | `"manipulation"` | Highest-scoring topic key |
| `matched_topics` | list | `["manipulation", "vla"]` | All matched topic keys |
| `open_access_url` | string | URL | Best open-access URL |
| `canonical_pdf_url` | string | URL | Direct PDF URL if available |
| `canonical_html_url` | string | URL | ar5iv HTML URL if available |
| `capture_status` | string | `"pending"`, `"succeeded"`, `"failed"` | Capture outcome (set after ingest) |
| `why_read` | string | | Auto-generated relevance note |
| `added_at` | string | ISO 8601 | When this inbox note was created |

---

## Source Evidence Note

Written by `source-ingest` during capture. Located at `sources/evidence/{date}/{citekey}.md`.

| Field | Type | Values / Example | Description |
|-------|------|-----------------|-------------|
| `type` | string | `"source-evidence"` | Note type identifier |
| `citekey` | string | `"smith2024vla"` | Stable bibliographic key |
| `paper_id` | string | | Original source paper ID |
| `doi` | string | | DOI if available |
| `arxiv_id` | string | | arXiv ID if available |
| `title` | string | | Paper title |
| `authors` | list | | Author names |
| `year` | int | | Publication year |
| `venue` | string | | Normalized venue name |
| `capture_method` | string | `"ar5iv_html_cleaned"`, `"pdf_text_recovered"` | How the paper was captured |
| `capture_fidelity` | string | `"high"`, `"medium"`, `"low"` | Confidence in capture quality |
| `capture_source` | string | `"ar5iv"`, `"pdf"` | Content origin |
| `page_state` | string | `"auto"` | Page management state |
| `zotero_mode` | string | `"local_first"`, `"web_api"`, `"disabled"` | Zotero mode at capture time |
| `zotero_status` | string | `"added"`, `"duplicate"`, `"skipped"`, `"error"` | Zotero handoff result |
| `zotero_key` | string | | Zotero item key if added |
| `zotero_uri` | string | | Zotero URI if added |
| `captured_at` | string | ISO 8601 | Capture timestamp |
| `source_assets_path` | string | relative path | Path to sidecar JSON |

---

## Wiki Paper Note

Written/updated by `source-ingest` (initial) and `knowledge-compile-publish` (compile). Located at `wiki/papers/{citekey}.md`.

| Field | Type | Values / Example | Description |
|-------|------|-----------------|-------------|
| `type` | string | `"wiki-paper"` | Note type identifier |
| `citekey` | string | `"smith2024vla"` | Bibliographic key |
| `title` | string | | Paper title |
| `authors_short` | string | `"Smith, Jones, et al."` | Up to 3 first authors |
| `year` | int | | Publication year |
| `venue` | string | | Normalized venue name |
| `page_state` | string | `"auto"`, `"manual"`, `"archived"` | `auto` = managed by compile; `manual` = human-controlled |
| `confidence` | float | `0.0–1.0` | Evidence confidence |
| `compile_version` | int | | Incremented on each EDC write |
| `last_compiled_at` | string | ISO 8601 | Last EDC Write timestamp |
| `manual_notes_present` | bool | | Whether manual sections exist |
| `source_evidence_path` | string | relative path | Path to source evidence file |
| `source_assets_path` | string | relative path | Path to sidecar JSON |
| `zotero_mode` | string | | Zotero mode at ingest time |
| `zotero_status` | string | | Zotero handoff result |
| `zotero_uri` | string | | Zotero URI if added |
| `zotero_key` | string | | Zotero item key if added |
| `capture_fidelity` | string | | Capture quality |
| `why_read` | string | | Relevance note |
| `summary` | string | | Paper abstract |
| `insights` | string | | Key insights from compile |
| `connections` | string | | Links to related work |

---

## Wiki Concept / Method / Topic Note

Written by `upsert_wiki_article` (initial stub) or `knowledge-compile-publish` (EDC compile). Located at `wiki/concepts/{slug}.md`, `wiki/methods/{slug}.md`, or `wiki/topics/{slug}.md`.

| Field | Type | Values / Example | Description |
|-------|------|-----------------|-------------|
| `type` | string | `"wiki-concept"`, `"wiki-method"`, `"wiki-topic"` | Note type identifier |
| `concept_id` | string | | Registry concept ID |
| `slug` | string | `"diffusion-policy"` | URL-safe slug |
| `canonical` | string | `"Diffusion Policy"` | Canonical display name |
| `concept_type` | string | `"concept"`, `"method"`, `"topic"` | Registry type |
| `aliases` | list | | Known alternative names |
| `paper_count` | int | | Papers referencing this concept |
| `page_state` | string | `"auto"`, `"manual"` | Page management state |
| `last_compiled_at` | string | ISO 8601 | Last EDC Write timestamp |

---

## Insights / Query Note

Written by the agent via `upsert_wiki_article` or direct file write. Located at `insights/queries/{slug}.md`.

| Field | Type | Values / Example | Description |
|-------|------|-----------------|-------------|
| `type` | string | `"query-note"` | Note type identifier |
| `question` | string | | The research question answered |
| `source_pages` | list | `["wiki/papers/smith2024.md"]` | Pages used to answer |
| `referenced_papers` | list | | Citekeys of referenced papers |
| `referenced_concepts` | list | | Concept slugs mentioned |
| `referenced_topics` | list | | Topic keys mentioned |
| `derived_actions` | list | | Suggested follow-up actions |
| `promotion_targets` | list | | Concepts/papers worth compiling next |
| `created_at` | string | ISO 8601 | Creation timestamp |

---

## Idea Note

Written/updated by the agent. Located at `insights/ideas/{idea-id}.md`.

| Field | Type | Values / Example | Description |
|-------|------|-----------------|-------------|
| `type` | string | `"idea-note"` | Note type identifier |
| `idea_state` | string | `active`, `rejected`, `parked`, `superseded` | Current lifecycle state |
| `date` | string | `"YYYY-MM-DD"` | Creation date |
| `topics` | list | `["manipulation"]` | Related topic keys |
| `related_papers` | list | `["smith2024vla"]` | Supporting citekeys |
| `related_concepts` | list | `["diffusion-policy"]` | Related concept slugs |
| `decision_reason` | string | | Why the idea was rejected/parked/superseded |
| `decision_at` | string | ISO 8601 | When the decision was made |
| `superseded_by` | string | | Idea ID of the superseding note |
| `status` | string | `"saved"` | File persistence status |

**`idea_state` valid transitions:**
- `active` → `rejected` (decided not to pursue)
- `active` → `parked` (deferred, may revisit)
- `active` → `superseded` (merged into a stronger idea)
- `rejected` / `parked` → `active` (reopened)
