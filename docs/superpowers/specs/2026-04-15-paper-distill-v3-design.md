# Paper Distill v3.0 Design

Date: 2026-04-15
Status: Draft approved in conversation, pending final user review of this written spec
Scope: v3.0 first release

## 1. Goal

Paper Distill v3.0 is a greenfield rewrite that replaces the v2.1 architecture with a simpler model:

- Markdown files are the only source of truth.
- `qmd` is the only supported knowledge search backend.
- Agents own reading, synthesis, linking, judgment, and concept evolution.
- Python tools own deterministic I/O, validation, atomic writes, and index scheduling.

The goal is not to preserve v2.1 behavior. The goal is to ship a cleaner system that is easier to reason about, less stateful, and more aligned with personal knowledge work in Obsidian.

## 2. Hard Rules

The following rules define the architecture and are not optional implementation details:

1. v3.0 is a one-shot cutover. No compatibility layer with v2.1 is required.
2. Markdown files inside the vault are the only truth for formal knowledge assets.
3. Hidden runtime state under `.state/` is allowed only for lightweight cache-like data, not for knowledge truth or compile orchestration.
4. `qmd` is a hard dependency. If `qmd` is unavailable, the system is not ready.
5. Formal knowledge search must go through the `qmd` facade. There is no filesystem or Python fallback for search.
6. Formal knowledge assets must be written through Python tools, not by direct agent file writes.
7. `wiki/papers` and `wiki/concepts` are agent-owned assets and are not intended for direct human editing.
8. File-write success is defined by successful atomic file persistence. Index update or embedding failures are warnings, not write rollback conditions.
9. New paper ingestion should not be blocked by failed concept compounding. Compounding failure is recoverable and must be surfaced explicitly.
10. v3.0 first release includes Phase 1-3 only. Phase 4 idea validation is out of scope for the first release.

## 3. Directory Model

The filesystem is organized by semantic layer rather than by implementation convenience.

### 3.1 Top-level layout

```text
Paper Distill/
├── vault-log.md
├── inbox/
├── raw/
│   └── evidence/
├── wiki/
│   ├── papers/
│   ├── concepts/
│   └── index.md
├── insights/
│   ├── ideas/
│   └── conversations/
├── exports/
│   └── presentations/
├── .state/
│   └── seen_papers.json
└── scripts/
    └── mcp_tools/
```

### 3.2 Directory responsibilities

- `vault-log.md`
  Append-only operation log. It is not a knowledge source and is excluded from `qmd`.

- `inbox/`
  Discovery-stage candidate stubs awaiting human approval. It is not a formal knowledge layer and is excluded from `qmd`.

- `raw/evidence/`
  Captured paper evidence in cleaned Markdown form. It belongs to the `raw` namespace and is excluded from default search.

- `wiki/papers/`
  Canonical distilled paper pages. This is part of the `canon` namespace.

- `wiki/concepts/`
  Flat concept graph pages. This is part of the `canon` namespace.

- `wiki/index.md`
  Human-facing Dataview or dashboard surface only. It is excluded from `qmd` and from backend truth.

- `insights/ideas/`
  Reserved formal idea assets. The directory exists in v3.0, but idea-validation workflows are out of scope for the first release.

- `insights/conversations/`
  Formal conversation-memory assets created from high-value agent-user exchanges. It belongs to the `insights` namespace.

- `exports/presentations/`
  Delivery artifacts. This directory is excluded from `qmd` and may be written directly by the agent.

- `.state/`
  Lightweight runtime cache only. The first release allows `.state/seen_papers.json` and similar operational caches, but does not allow hidden knowledge state, JSON IR, or orchestration state machines.

### 3.3 Namespace mapping

`qmd` namespaces are fixed by directory:

- `canon`
  `wiki/papers/`, `wiki/concepts/`

- `insights`
  `insights/ideas/`, `insights/conversations/`

- `raw`
  `raw/evidence/`

Explicit exclusions:

- `inbox/`
- `exports/`
- `vault-log.md`
- `.state/`
- `wiki/index.md`

## 4. Naming Rules

### 4.1 Paper files

Paper files use a mixed human-readable and stable-ID naming scheme:

- `wiki/papers/<title-slug>--<paper-id>.md`
- `raw/evidence/<title-slug>--<paper-id>.md`

Example:

- `attention-is-all-you-need--arxiv-1706.03762.md`

This keeps filenames readable in Obsidian while preventing ambiguity and making re-ingest safe.

### 4.2 Concept files

Concept files use human-readable canonical slugs:

- `wiki/concepts/transformer.md`
- `wiki/concepts/vision-transformer.md`

Concept pages are internal knowledge objects, so readability is preferred over external-ID style naming.

## 5. Write Ownership

### 5.1 Human-modifiable

- `inbox/` candidate stubs, including adding `#approved`

### 5.2 Python-tool write path required

- `raw/evidence/`
- `wiki/papers/`
- `wiki/concepts/`
- `insights/ideas/`
- `insights/conversations/`
- `vault-log.md`

### 5.3 Agent direct-write exception

- `exports/presentations/`

## 6. Tool Facade and Boundaries

v3.0 uses a narrow facade. Agents only see a few high-level tools.

### 6.1 Read tools

- `kb_search(query, scope)`
  Formal semantic search. Must use `qmd`. Default scope is `canon`. Supported first-release scopes are `canon`, `insights`, and `raw`. Results must include `qmd_context`.

- `kb_get(id_or_path)`
  Direct retrieval of a single document by stable identifier or explicit path. This returns the current file truth, including full frontmatter and body.

- `check_concept_alias(name)`
  Lightweight canonicalization helper backed by Python parsing of concept names and aliases. This is not a semantic search tool.

### 6.2 Discovery and ingestion tools

- `discover_papers(...)`
  Discovers candidate papers from external sources, deduplicates against `.state/seen_papers.json`, scores them, writes inbox stubs, and reports a summary.

- `ingest_and_read(input)`
  Accepts either approved inbox items or a direct URL. It captures and writes raw evidence, then returns the captured content to the agent for immediate reading and synthesis.

### 6.3 Write tools

- `upsert_wiki_page(page_type, target, frontmatter, body, options?)`
  Writes formal knowledge assets safely. The tool validates minimal frontmatter, performs atomic persistence, and schedules index work. It does not inject links, infer content structure, or patch sections intelligently.

- `merge_concept(old, new)`
  Performs high-impact concept consolidation. It replaces old links with new ones across the vault, updates aliases on the canonical concept, and triggers index maintenance.

### 6.4 Maintenance tools

- `kb_update_index`
  Explicit maintenance-only index refresh.

- `kb_reembed_force`
  Explicit maintenance-only embedding rebuild.

- `/lint`-backing health tool
  Reports structural and content-quality issues without silently mutating the library.

### 6.5 Editing model

`upsert_wiki_page` is an entire-document replacement API:

- The agent must read the current page with `kb_get` when updating an existing asset.
- The agent constructs the new full page in memory.
- The tool writes the new full frontmatter and full body atomically.

The first release does not support section-level patch APIs.

## 7. Core Workflows

### 7.1 Discovery and inbox

1. `/discover` calls `discover_papers`.
2. The tool queries external sources, deduplicates using `.state/seen_papers.json`, scores results, and writes inbox stubs.
3. The user reviews inbox files in Obsidian.
4. Approval is represented only by `#approved` in the file body.

### 7.2 Ingest and compile

There are two supported first-release entry paths:

- `/ingest approved`
- `/ingest <url>`

Flow:

1. `ingest_and_read` validates approved inbox input or accepts a direct URL.
2. The tool captures and writes `raw/evidence`.
3. The agent immediately reads the raw content and produces the `7 CRGP sections`.
4. The agent uses sparse inline `[[links]]`, not footer link dumps.
5. The agent uses `check_concept_alias` to normalize concept references.
6. The agent writes the paper page with `upsert_wiki_page`.
7. The agent creates a concept page only when it judges that the concept is core, not merely mentioned.
8. If the new paper materially challenges an existing concept, the agent attempts concept compounding by reading the old concept page with `kb_get`, updating its `Tension` section in memory, and writing the full page back through `upsert_wiki_page`.

### 7.3 Maintenance and memory

- `/lint` reports dead links, malformed links, alias ambiguity, link density issues, repeated in-paragraph links, template-like footer link spam, and suspiciously large frontmatter.
- `merge_concept` is allowed for ordinary agents when confidence is high enough.
- The agent may proactively write `insights/conversations/` when a conversation produces a high-value research insight.

## 8. Document Contracts

Frontmatter stores only retrieval, status, and traceability essentials. The body stores the actual knowledge.

### 8.1 Inbox stub

Minimum frontmatter:

```yaml
type: inbox_stub
paper_id: arxiv:1706.03762
title: Attention Is All You Need
source_url: https://arxiv.org/abs/1706.03762
discovered_at: "2026-04-15"
score: 92
```

Rules:

- Body contains lightweight summary and review cues.
- Approval truth is `#approved` in the body.
- No mirrored approval status is maintained in frontmatter.

### 8.2 Raw evidence

Minimum frontmatter:

```yaml
type: raw_evidence
paper_id: arxiv:1706.03762
title: Attention Is All You Need
source_url: https://arxiv.org/abs/1706.03762
captured_at: "2026-04-15"
content_hash: "..."
```

Rules:

- Body stores cleaned source Markdown.
- No knowledge links or summaries are injected.
- Raw evidence is logically read-only, but the same path may be overwritten when the capture pipeline is fixed, as long as the `paper_id` remains the same.

### 8.3 Paper page

Minimum frontmatter:

```yaml
type: paper
paper_id: arxiv:1706.03762
year: 2017
status: distilled
key_concepts_topk: [Transformer, Self-Attention, Sequence Modeling]
source_layer: canon
```

Rules:

- Body follows the `7 CRGP sections`.
- Sparse inline links are required where semantically useful.
- Footer-scale link dumping is forbidden.

### 8.4 Concept page

Minimum frontmatter:

```yaml
type: concept
aliases: [变换器, Transformer模型]
status: mature
last_updated: "2026-04-15"
last_tension_update: "2026-04-15"
sources_topk: ["arxiv:1706.03762"]
```

Body shape:

- `# <Concept>`
- `## Definition`
- `## Core Claims`
- `## Boundaries`
- `## Tension`
- `## Related Top-K`

Rules:

- Only core concepts receive pages.
- The `Tension` section is the primary target for compounding updates.

### 8.5 Conversation memory

Minimum frontmatter:

```yaml
type: conversation
captured_at: "2026-04-15T18:00:00+08:00"
source_thread: current-thread
related_concepts_topk: [Transformer, Sparse Linking]
source_layer: insights
```

Rules:

- This stores distilled insight, not verbatim full chat transcript.
- Sparse inline links are allowed and encouraged.

### 8.6 Idea page

Idea assets are reserved for a later phase, but the model is defined now for stability:

```yaml
type: idea
status: draft
related_concepts_topk: [Vision Transformer, Linear Attention]
evidence_anchors_topk: ["arxiv:1706.03762"]
novelty_check: pending
source_layer: insights
```

### 8.7 Global content constraints

- Frontmatter arrays must stay Top-K sized.
- Frontmatter must not contain long summaries.
- Frontmatter reference fields prefer stable IDs over `[[...]]`.
- Canon pages prioritize verifiable facts and tension over derived dashboard-like lists.

## 9. Search, Get, and Consistency Model

v3.0 defines two different read semantics:

- `get`
  Reads current file truth directly.

- `search`
  Reads the `qmd` search view.

This means the system explicitly allows a short window where:

- `kb_get` can already see a newly written file
- `kb_search` may not yet reflect the file if `update()` and `embed()` have not caught up

This is expected behavior, not a defect.

### 9.1 Write-after effects

After a successful formal write:

1. The target file is validated and written atomically.
2. The write is considered successful immediately after persistence.
3. Debounced `update()` is scheduled.
4. `update()` may return `needsEmbedding`.
5. Embedding may be completed asynchronously.

### 9.2 Success and failure semantics

- File persisted, index lagging:
  success with warning

- File not persisted:
  write failure

- `qmd` unavailable:
  system not ready, search failure

- Compounding update failed after paper write:
  paper success with warning

## 10. Readiness and Logging

### 10.1 Readiness states

- `ready`
  `qmd` available, namespaces mounted, no blocking search issue

- `degraded`
  file reads and writes work, but indexing or embedding warnings exist

- `not_ready`
  `qmd` unavailable or unusable for formal search

`kb_get` may still work in degraded or not-ready states for diagnostic use, but the system as a whole remains not ready if `qmd` is unavailable.

### 10.2 `vault-log.md`

`vault-log.md` is append-only and uses a simple table:

```markdown
# Vault Operation Log

| Timestamp | Action | Resource ID | Status | Notes |
|-----------|--------|-------------|--------|-------|
```

Expected action families include:

- `DISCOVER`
- `INGEST`
- `UPSERT_PAPER`
- `UPSERT_CONCEPT`
- `UPSERT_CONVERSATION`
- `MERGE`
- `REINDEX`
- `REEMBED`
- `WARN`
- `FAIL`

## 11. Command Surface

The first-release command surface is intentionally small:

- `/discover`
- `/inbox`
- `/ingest`
- `/search`
- `/get`
- `/lint`
- `/status`

Internal or maintenance-oriented commands may exist, but they are not the primary user-facing workflow.

Commands intentionally removed from the v3.0 mental model:

- `/compile`
- `/query`
- `/process-inbox`
- `/ideas`

## 12. First-release Scope

### 12.1 In scope

- Phase 1 Discovery and Inbox
- Phase 2 Ingestion and Compilation
- Phase 3 Maintenance and Conversation Memory
- `kb_search`
- `kb_get`
- readiness reporting
- index warning surfacing

### 12.2 Out of scope

- v2.1 compatibility
- JSON IR
- SQLite compile-state orchestration
- concept subtrees such as `wiki/methods/` and `wiki/topics/`
- automatic footer link blocks
- `qmd` fallback
- Phase 4 idea validation and novelty-check workflow

## 13. Acceptance Criteria

v3.0 first release is acceptable only if the following behaviors hold:

1. Without `qmd`, the system reports `not_ready` and does not pretend formal search still works.
2. `/discover` writes inbox stubs and suppresses duplicates via `.state/seen_papers.json`.
3. Only inbox files containing `#approved` are eligible for `/ingest approved`.
4. `/ingest <url>` and `/ingest approved` both write valid raw evidence on successful capture.
5. Each ingested paper can be distilled into a `wiki/papers` page using `7 CRGP sections`.
6. Sparse inline links appear in paper and concept bodies without template-like footer dumping.
7. Only core concepts are promoted to concept pages.
8. Concept compounding attempts occur when material tension is found; paper ingest still succeeds if the compounding update fails.
9. `/search` uses `qmd` only.
10. `/get` returns current document truth by identifier or explicit path.
11. `/lint` reports structural issues without silently rewriting the vault.
12. High-value conversations can be written as formal `insights/conversations` assets.

## 14. Test Strategy

The first release requires:

- unit tests for naming, frontmatter validation, deduplication, alias resolution, and merge behavior
- integration tests for `/discover`, approval, ingest, canonical write, compounding warning behavior, `/search`, and `/get`
- failure-path tests for missing `qmd`, failed capture, failed `update()`, failed embedding, and partial merge fallout
- acceptance tests using at least one or two real-paper flows

## 15. Release Definition

Paper Distill v3.0 exists when the system can reliably complete the following closed loop under a ready `qmd` environment:

`discover -> approve -> ingest -> canon compilation -> maintenance -> conversation memory`

and all formal knowledge assets remain Markdown-first rather than database-first.
