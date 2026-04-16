# Paper Distill v3 Repository Purity Design

Date: 2026-04-16
Status: Draft approved in conversation, pending final user review of this written spec
Scope: Repository cleanup for the current v3 release line

## 1. Goal

The repository should describe and ship one thing only: the current Paper Distill v3 system.

This cleanup removes retired architecture residue from runtime code, tests, and documentation so that:

- the visible command surface is the current v3 command set,
- the visible MCP surface is the current v3 tool set,
- the repository no longer carries dormant fallback systems or historical scaffolding,
- contributor-facing docs explain the current architecture directly, without transitional narration.

Git history is the archive. The working tree should stay focused on present-tense behavior.

## 2. Non-Goals

This cleanup does not:

- add new end-user features,
- preserve compatibility aliases or migration shims,
- introduce a second implementation path for search, retrieval, or writes,
- expand beyond the current Phase 1-3 product boundary.

## 3. Purity Rules

The cleanup follows these rules:

1. Delete retired implementation paths instead of hiding them behind wrappers.
2. Keep a file only if it directly serves the current v3 runtime, tests, or operator documentation.
3. Rewrite shared docs that still matter; delete docs that only exist to explain retired behavior.
4. Treat historical planning notes the same way as product docs: keep only pure v3 narration.
5. Preserve the current public surface while simplifying internal structure behind it.

## 4. Current Public Surface

The repository after cleanup should expose only the following public interfaces.

### 4.1 Commands

- `/discover`
- `/get`
- `/inbox`
- `/ingest`
- `/lint`
- `/search`
- `/status`

### 4.2 MCP tools

- `check_concept_alias`
- `discover_papers`
- `ingest_and_read`
- `kb_get`
- `kb_reembed_force`
- `kb_search`
- `kb_update_index`
- `lint_vault`
- `merge_concept`
- `status`
- `upsert_wiki_page`

### 4.3 Architectural invariants

- `qmd` is a hard dependency for knowledge search.
- `kb_search` and `kb_get` are the only knowledge read facades.
- Formal knowledge assets are written through Python tools.
- `exports/` remains the only direct-write exception for delivery artifacts.

## 5. Cleanup Scope

### 5.1 Runtime code

Cleanup applies to:

- the server entrypoint and registration graph,
- tool facade modules,
- runtime helpers and adapters,
- configuration defaults and operator-facing strings,
- any unregistered or unreachable module that exists only to support retired behavior.

The desired end state is a narrow runtime graph whose modules can be explained in terms of the current discovery, ingest, retrieval, knowledge-write, alias, and health flows.

### 5.2 Tests

The test suite should retain:

- behavior tests for the current public tools and commands,
- storage and layout tests for the current vault model,
- QMD integration and bootstrap tests required by the current architecture,
- regression guards that prevent retired names or paths from reappearing.

Tests that exist only to validate retired flows should be deleted.

### 5.3 Documentation

Documentation cleanup covers:

- top-level product and operator docs under `docs/`,
- development docs under `docs/superpowers/specs/` and `docs/superpowers/plans/`,
- any reference file whose main value is describing retired commands, tools, layouts, or workflows.

For docs that still matter to v3 users, the content should be rewritten in present tense around the current architecture, including empty-repository setup and QMD initialization.

### 5.4 Repository hygiene

Cleanup also removes:

- checked-in cache artifacts such as `__pycache__/`,
- obsolete generated files that no longer serve the current product,
- stale references that imply the repository supports multiple architectural eras at once.

## 6. Retention Policy

Each candidate file falls into one of three buckets:

### 6.1 Keep as-is

Keep files that are already aligned with the current v3 runtime and documentation model.

### 6.2 Rewrite in place

Rewrite files that remain useful but still carry retired naming, assumptions, or examples. Typical cases:

- docs that should describe the current command or tool surface,
- thin facade modules that currently define extra retired handlers beside the live ones,
- tests that should remain but need stronger v3-only assertions.

### 6.3 Delete outright

Delete files when their primary purpose is any of the following:

- providing retired public names,
- preserving fallback query or write paths,
- validating retired workflows,
- documenting behavior that no longer exists,
- carrying generated residue with no source-of-truth value.

## 7. Verification Strategy

The cleanup is complete only when both behavior and repository shape are validated.

### 7.1 Behavioral verification

- Run the focused v3 test modules that define the current public surface.
- Run the full test suite after the deletions settle.
- Run a compile pass over `server/` and `tests/`.
- Run an MCP smoke check to confirm the live tool registry still exposes exactly the current tool set.

### 7.2 Shape verification

Add or tighten guardrails that assert:

- the command directory contains only the current v3 commands,
- the live MCP tool list contains only the approved v3 tools,
- the vault layout expectation includes `insights/ideas/`,
- DOI-style paper identifiers are sanitized safely for filenames,
- retired public identifiers do not reappear in the repository,
- checked-in cache directories do not reappear.

## 8. Execution Order

The cleanup should happen in this order:

1. Strengthen guard tests so the desired repository shape is executable.
2. Simplify the live registration and facade modules to the current public surface only.
3. Delete unreachable runtime leftovers and the tests that target them.
4. Rewrite or delete documentation until the doc set reads as pure v3.
5. Remove repository residue, rerun verification, and confirm the final tree is coherent.

## 9. Risks and Mitigations

### 9.1 Risk: deleting a module that is still transitively required

Mitigation:

- inspect imports before deletion,
- keep public-surface tests green at each stage,
- use repository search to confirm no live registration path still points at the file.

### 9.2 Risk: documentation cleanup drifts from actual behavior

Mitigation:

- rewrite docs after runtime cleanup settles,
- validate docs against the final live command and tool lists,
- keep bootstrap instructions aligned with the real empty-repository setup flow.

### 9.3 Risk: purity checks become too weak

Mitigation:

- encode repository-shape assertions in tests,
- keep the banned-surface checks focused on public identifiers and cache residue,
- prefer exact set assertions over loose substring checks when possible.

## 10. Success Criteria

The cleanup is successful when all of the following are true:

- the repository exposes only the approved v3 commands and MCP tools,
- runtime code no longer contains dormant fallback or retired public handlers,
- tests cover the current architecture and no longer validate retired flows,
- docs describe only the current v3 model, including developer planning docs,
- verification passes end-to-end without needing compatibility behavior.
