# QMD CLI Boundary Design

Date: 2026-04-16
Status: Approved for planning

## Goal

Make QMD CLI the only read and index-maintenance interface in Paper Distill v3.

After this change:

- QMD CLI is the primary source for search, document retrieval, collection health, index refresh, and embedding refresh.
- Paper Distill MCP exposes only business operations that QMD does not know how to perform.
- `paper-distill-admin bootstrap` remains as the one-time initialization entry for an empty vault, but it only creates the v3 layout and initializes QMD collections and contexts.

`docs/qmd-cli.md` will state:

> QMD CLI is the primary source; command details follow the runtime output of `qmd --help`.

## Final Boundary

### QMD owns

- Search across vault assets
- Single-document retrieval
- Collection and context management
- Index health inspection
- Re-indexing
- Embedding refresh

These actions are performed directly through QMD CLI, not through Paper Distill MCP wrappers.

### Paper Distill owns

- Discovery across paper sources and inbox stub creation
- Approved arXiv capture into `raw/evidence/`
- Deterministic concept alias checks
- Deterministic page writes for `wiki/*` and `insights/*`
- Concept merge and link rewriting
- Vault linting for Paper Distill-specific Markdown and frontmatter rules

## Runtime Surface

### Retained MCP tools

- `discover_papers`
- `ingest_and_read`
- `check_concept_alias`
- `upsert_wiki_page`
- `merge_concept`
- `lint_vault`

### Removed MCP tools

- `kb_search`
- `kb_get`
- `status`
- `kb_update_index`
- `kb_reembed_force`

The MCP smoke surface must shrink from 11 tools to 6 tools.

## Bootstrap

`paper-distill-admin bootstrap` remains in the repository.

Its scope is limited to:

- creating the v3 directory layout,
- ensuring the five QMD collections exist and point at the correct paths,
- ensuring the expected QMD contexts exist,
- returning a clear initialization report.

It does not act as a day-to-day read path, query path, or index-maintenance interface.

### Required collections

- `canon-papers` -> `wiki/papers`
- `canon-concepts` -> `wiki/concepts`
- `insights-conversations` -> `insights/conversations`
- `insights-ideas` -> `insights/ideas`
- `raw-evidence` -> `raw/evidence`

### Required contexts

- `qmd://canon-papers` -> `Canonical distilled papers`
- `qmd://canon-concepts` -> `Canonical concept pages`
- `qmd://insights-conversations` -> `Conversation-derived research insights`
- `qmd://insights-ideas` -> `Idea drafts and later validation assets`
- `qmd://raw-evidence` -> `Raw captured evidence and source markdown`

## Agent Learning Surface

### `docs/qmd-cli.md`

Create `docs/qmd-cli.md` as the single repository guide for QMD usage inside Paper Distill.

It will include:

- the primary-source statement pointing agents to runtime `qmd --help`,
- the five collection names and what each collection means in this repository,
- recommended Paper Distill command patterns for:
  - `qmd query`
  - `qmd get`
  - `qmd status`
  - `qmd update`
  - `qmd embed -f`
  - `qmd collection ...`
  - `qmd context ...`
  - `qmd ls`
- a concise “Paper Distill main path” section,
- an appendix covering additional official QMD commands that are available but not part of the normal Paper Distill path.

The document should be comprehensive enough for agents to work effectively, but it should keep the main path visually distinct from optional commands.

### Skills

`skills/*` will teach agents to:

- use Paper Distill MCP for business actions,
- use QMD CLI directly for reading and index maintenance,
- consult `docs/qmd-cli.md`,
- consult runtime `qmd --help` and subcommand help when command details are uncertain.

### Commands

`commands/` will keep only business command documents.

The retained command set is:

- `discover.md`
- `inbox.md`
- `ingest.md`
- `lint.md`

Read and index-maintenance instructions move out of `commands/` and into `docs/qmd-cli.md` plus the skills.

## Write Semantics

`upsert_wiki_page` and `merge_concept` must stop invoking any QMD command internally.

A successful write means:

- the target file content or links were updated correctly,
- the returned payload includes a follow-up reminder that QMD refresh is a separate step.

Recommended follow-up messaging:

- run `qmd update` after all writes in the current round finish,
- run `qmd embed -f` after all writes finish if semantic retrieval must reflect the new state immediately.

The write tools do not own index refresh timing anymore.

## Repository Code Changes

### Remove read/index wrappers from MCP

- remove `server/tools_core.py`
- remove registration of the five removed tools from `server/server.py`
- trim `server/tools_knowledge.py` to business tools only

### Reshape QMD support code

Keep only the QMD bootstrap support needed by `paper-distill-admin bootstrap`.

Read and maintenance wrapper helpers should no longer exist as runtime interfaces used by MCP tools.

If helpful for clarity, the bootstrap logic may move into a dedicated module such as `server/qmd_bootstrap.py`.

### Keep write and health business logic

- `server/v3_store.py` stays, but drops QMD update side effects
- `server/v3_health.py` stays, but `merge_concept_v3()` drops QMD update and re-embed side effects
- `server/v3_discovery.py`, `server/v3_ingest.py`, alias logic, and lint logic remain as business-layer code

## Tests

### Tool surface

- update MCP surface tests to require exactly the six retained business tools
- fail if any removed QMD wrapper tool reappears

### Command inventory

- assert the retained business command set only

### Skills and docs

- assert docs and skills teach QMD CLI directly
- assert docs and skills point to `docs/qmd-cli.md`
- assert docs and skills no longer teach `kb_search`, `kb_get`, `status`, `kb_update_index`, or `kb_reembed_force`

### Write behavior

- update write tests so they no longer expect internal QMD update or re-embed calls
- assert returned follow-up guidance instead

### Bootstrap

- strengthen bootstrap tests for:
  - empty-vault creation,
  - collection creation,
  - context creation,
  - wrong-path remount,
  - repeated-run idempotence

## Non-Goals

- no new Paper Distill wrapper around QMD MCP
- no secondary read path besides QMD CLI
- no automatic QMD refresh hidden inside business write tools

## Completion Criteria

This design is complete when:

- only six business MCP tools remain,
- all read and index-maintenance guidance routes agents to QMD CLI,
- `docs/qmd-cli.md` becomes the single repository reference for QMD usage,
- bootstrap remains the only initialization shortcut,
- business write tools stop invoking QMD commands,
- tests enforce the new boundary.
