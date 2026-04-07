# Phase 3 Maintenance Controller Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement a safe, idempotent Phase 3 maintenance system for Paper Distill that protects user-authored wiki content, executes merge/promote/refresh tasks through controllers, propagates dependency invalidation, and enriches Compile IR for stronger Idea generation.

**Architecture:** Upgrade `commit_compile_result()` into a managed-block patch engine, extend the SQLite state model to track section hashes and richer task status, add execution controllers in `server/maintenance.py`, and expand IR/tension aggregation so idea-generation consumes stronger structured signals. Land the work in tightly scoped slices so write safety is proven before any automated maintenance executor mutates wiki pages.

**Tech Stack:** Python 3.10+, `sqlite3`, `uv`, `pytest`, `unittest`, existing MCP server tools

---

### Task 1: Implement managed-block parsing and safe patching

**Files:**
- Modify: `server/compile_ir.py`
- Modify: `server/database.py`
- Create: `tests/test_compile_patch_engine.py`

- [ ] Add helpers in `server/compile_ir.py` to parse markdown into managed blocks and user blocks.
- [ ] Add support for per-block identities like `<!-- managed:start section=context -->`.
- [ ] Extend `compile_state` persistence to store per-block hashes (for example `managed_hashes_json`).
- [ ] Update `commit_compile_result()` to:
- [ ] read the existing page when present
- [ ] compare stored managed hashes against current managed blocks
- [ ] patch unchanged or safely mappable managed blocks
- [ ] preserve `## My Notes` and all unmanaged content verbatim
- [ ] return `conflict_detected` without overwriting when managed content was user-edited incompatibly
- [ ] Add regression tests for:
- [ ] fresh write
- [ ] preserving user blocks
- [ ] conflict detection on changed managed content
- [ ] safe patch when block identity is stable

Run:
```bash
uv run pytest -q tests/test_compile_patch_engine.py tests/test_compile_ir.py
```

### Task 2: Expand queue/task state model and execution plumbing

**Files:**
- Modify: `server/database.py`
- Modify: `server/maintenance.py`
- Modify: `server/server.py`
- Create: `tests/test_maintenance_execution.py`

- [ ] Extend queue status model to include `blocked` and `failed`.
- [ ] Add helpers in `server/maintenance.py` for claiming a confirmed task into `processing` and for finishing into `done`/`blocked`/`failed`.
- [ ] Add MCP tools in `server/server.py`:
- [ ] `execute_maintenance_task(task_id)`
- [ ] optionally `run_maintenance_controller(limit=1)` if useful for orchestration
- [ ] Keep existing confirm/reject flows intact.
- [ ] Add tests for:
- [ ] legal status transitions
- [ ] invalid transitions
- [ ] repeated execution attempts

Run:
```bash
uv run pytest -q tests/test_maintenance_execution.py tests/test_registry_maintenance.py
```

### Task 3: Implement `execute_merge()` with dependency propagation

**Files:**
- Modify: `server/maintenance.py`
- Modify: `server/concept_registry.py`
- Modify: `server/compile_ir.py`
- Create: `tests/test_execute_merge.py`

- [ ] Implement `execute_merge(vault_path, task_id)`:
- [ ] validate task payload
- [ ] call `merge_concepts()`
- [ ] find all dependent pages via `compile_deps`
- [ ] refresh those pages through Resolve + Write or mark blocked on conflict
- [ ] make the executor idempotent when merge was already applied
- [ ] Add a helper for reverse dependency lookup from `compile_deps`.
- [ ] Update task completion status and execution summary.
- [ ] Add tests that verify:
- [ ] dependent pages are selected correctly
- [ ] unrelated pages are untouched
- [ ] repeated merge execution is safe

Run:
```bash
uv run pytest -q tests/test_execute_merge.py tests/test_registry_maintenance.py tests/test_compile_ir.py
```

### Task 4: Implement `execute_promote()` for concept-to-topic evolution

**Files:**
- Modify: `server/maintenance.py`
- Modify: `server/concept_registry.py`
- Modify: `server/compile_ir.py`
- Create: `tests/test_execute_promote.py`

- [ ] Implement `execute_promote(vault_path, task_id)`:
- [ ] promote registry type/version
- [ ] create or refresh the target topic page
- [ ] update affected dependencies
- [ ] refresh dependent concept/paper/topic pages
- [ ] ensure idempotent behavior when already promoted
- [ ] Add tests for:
- [ ] promotion state change
- [ ] topic page creation/refresh
- [ ] repeated promotion no-op safety

Run:
```bash
uv run pytest -q tests/test_execute_promote.py tests/test_registry_maintenance.py tests/test_compile_ir.py
```

### Task 5: Implement `execute_refresh()` and base refresh strategy

**Files:**
- Modify: `server/maintenance.py`
- Modify: `server/vault_lint.py`
- Create: `tests/test_execute_refresh.py`

- [ ] Implement `execute_refresh(vault_path, task_id)` for `stale_topic_refresh` tasks.
- [ ] Refresh scope should come from explicit deps, not fuzzy full-vault scans where possible.
- [ ] Support at least the base topic refresh behavior:
- [ ] gather relevant papers/concepts/methods
- [ ] re-render managed sections
- [ ] preserve user content via the patch engine
- [ ] mark blocked on conflict
- [ ] Keep advanced trigger logic separate from the executor.
- [ ] Add tests for:
- [ ] refreshing a stale topic page
- [ ] preserving `## My Notes`
- [ ] blocking on conflict

Run:
```bash
uv run pytest -q tests/test_execute_refresh.py tests/test_compile_ir.py tests/test_registry_maintenance.py
```

### Task 6: Expand Compile IR schema for stronger ideation signals

**Files:**
- Modify: `server/compile_ir.py`
- Modify: `server/vault_lint.py`
- Modify: `skills/wiki-compile/SKILL.md`
- Modify: `skills/idea-generator/SKILL.md`
- Modify: `tests/test_compile_ir.py`

- [ ] Extend `validate_ir()` and related comments/docs to require or support:
- [ ] `failure_modes`
- [ ] `transfer_constraints`
- [ ] `benchmark_scope`
- [ ] `claimed_novelty`
- [ ] Require structured tension entries to support `claim`, `source_ref`, and optionally `section`, `confidence`.
- [ ] Extend `aggregate_tension_signals()` to aggregate the new fields where useful.
- [ ] Thread the new IR-derived signals into `analyze_knowledge_graph_sync()`.
- [ ] Update skills so agents know how to produce and consume the richer schema.
- [ ] Add tests for schema validation and signal aggregation on the new fields.

Run:
```bash
uv run pytest -q tests/test_compile_ir.py tests/test_registry_maintenance.py tests/test_compile_patch_engine.py
```

### Task 7: Add advanced trigger candidate generation

**Files:**
- Modify: `server/vault_lint.py`
- Modify: `server/compile_ir.py`
- Modify: `server/server.py`
- Create: `tests/test_trigger_candidates.py`

- [ ] Add deterministic or mostly deterministic candidate generation for:
- [ ] recurring limitation spikes
- [ ] cross-cluster bridges
- [ ] benchmark evaluation splits
- [ ] contradiction candidates (bounded heuristic candidate generation only)
- [ ] Expose a new MCP tool to inspect these trigger candidates if needed.
- [ ] Keep candidate generation separate from actual execution.
- [ ] Add tests that prove candidate generation works on controlled fixtures.

Run:
```bash
uv run pytest -q tests/test_trigger_candidates.py tests/test_compile_ir.py tests/test_registry_maintenance.py
```

### Task 8: Integrate adjudication and wire Phase 3 into skills

**Files:**
- Modify: `server/server.py`
- Modify: `skills/wiki-compile/SKILL.md`
- Modify: `skills/wiki-lint/SKILL.md`
- Modify: `skills/idea-generator/SKILL.md`

- [ ] Add explicit tool/docs support so agents can:
- [ ] inspect confirmed maintenance tasks
- [ ] execute a single task safely
- [ ] inspect trigger candidates separately from the queue
- [ ] Update `wiki-compile` skill so it reflects real controller capabilities rather than aspirational ones.
- [ ] Update `wiki-lint` skill to describe the explicit reconcile -> confirm -> execute loop.
- [ ] Update `idea-generator` skill to consume:
- [ ] graph-based gaps
- [ ] IR-based tension signals
- [ ] trigger candidates

Run:
```bash
uv run pytest -q tests/
```

### Task 9: Final verification and migration guidance

**Files:**
- Modify: `docs/plan-v2-phase3-followup.md`
- Modify: `docs/plan-v2-implementation.md`
- Optionally modify: `README.md`

- [ ] Document what is now complete in Phase 3A vs Phase 3B.
- [ ] Record any remaining limitations or intentionally deferred work.
- [ ] Add migration notes for older vaults that have registry/IR but not refreshed topic pages.
- [ ] Run the full test suite and record the exact result.

Run:
```bash
uv run pytest -q tests/
```

