# TODO Status

This page records whether the refactor TODO has been completed against the current implementation.

## Completed

- [x] `wiki/papers/` is the canonical visible paper workspace.
- [x] `sources/evidence/` is the only default source evidence layer.
- [x] `query-library` uses an Obsidian-first adapter with filesystem fallback.
- [x] Query responses report provider metadata and fallback state.
- [x] Real Obsidian CLI/Bases behavior was verified against the local vault on 2026-04-11.
- [x] Obsidian CLI is the only retained Obsidian provider family.
- [x] Native Obsidian CLI output is normalized inside `server/obsidian_query.py`, so `query-library` can use the built-in CLI without a wrapper command.
- [x] `_index.md` files are no longer treated as backend truth; `query-library` is the machine interface.
- [x] Generated dashboard/productization logic was removed; `index.md` and `_index.md` are minimal landing notes only.
- [x] Durable mutation runtime tables and publish journal tables were removed from the active schema.
- [x] `server/runtime.py` and `server/publish.py` were removed.
- [x] Memory append, compile, promotion, and dialogue capture use direct-write paths.
- [x] Hidden compile IR is stored under `.state/ir/`.
- [x] `ResearchItem` provides a lightweight shared paper entity contract.
- [x] `source-ingest` writes `sources/evidence` and `wiki/papers` and returns final field names only.
- [x] `wiki/papers` frontmatter includes `page_state`, `confidence`, `last_compiled_at`, and `manual_notes_present`.
- [x] Compile preserves manual sections while refreshing managed sections.
- [x] Idea notes are the default visible idea asset under `insights/ideas/`.
- [x] Idea verification writes only the canonical idea note by default.
- [x] Idea negative knowledge lives in the idea note through fields such as `idea_state`, `decision_reason`, `decision_at`, and `superseded_by`.
- [x] Idea creation includes a lightweight similar-idea check.
- [x] `insights/queries/` is no longer the default sink for every idea-analysis run.
- [x] `server/server.py` is a thin FastMCP entrypoint with domain tool registration.
- [x] README, docs, templates, commands, and skills now describe the `sources/evidence -> wiki/papers` model.
- [x] Skills were merged into the medium-grained workflows `paper-intake`, `knowledge-workbench`, and `idea-workbench`.
- [x] Concept abbreviation auto-merge whitelist is externalized to `paper_distill.concept_registry.abbreviation_whitelist`.

## Partially Completed

- [~] Obsidian is preferred for structured querying, but filesystem scan remains the supported offline fallback.
- [~] Obsidian CLI is used only for the vault currently open in Obsidian; other vaults intentionally fall back to filesystem scan.
- [~] SQLite responsibility has been reduced, but `compile_state` and `compile_deps` are still retained for compile dependency/version tracking.
- [~] `_index.md` files are still seeded as minimal directory landing files for Obsidian usability.
- [~] `server/idea_verification.py` is no longer a snapshot/runtime lifecycle; the module now exists only as the note-first idea writer.
- [~] Write paths are more constrained, but some specialized writers still live across multiple domain modules.

## Deferred

- [ ] Decision on whether `compile_state` and `compile_deps` should eventually move out of SQLite.
- [ ] Moving `concept_registry` or `maintenance_queue` to files, if a future file-first design proves simpler.

## Latest Comprehensive Verification

Run after the implementation cutover, Obsidian CLI validation, documentation update, and final naming cleanup:

```text
uv run pytest -q
195 passed

uv run python -m compileall -q server tests
exit 0

git diff --check
exit 0

MCP surface smoke check
tool_count=32
required_tools_present=idea-discover,knowledge-compile-publish,paper-distill-extract,query-library,source-discover,source-ingest

uv build
Successfully built dist/paper_distill_server-2.1.0.tar.gz
Successfully built dist/paper_distill_server-2.1.0-py3-none-any.whl

Obsidian CLI validation
Obsidian 1.12.4 CLI/Bases visible-vault probes passed for file listing,
keyword search, properties, tags, and `base:query`.
Hidden `.state` probes were not indexed by Obsidian, as expected.
Native Obsidian CLI adapter smoke check reported `provider=official_cli`,
`fallback_used=False`, and zero-item stats for `papers`, `source_evidence`, and
`inbox` in the currently open local vault.
```
