# Phase 3 Maintenance Controller Design

## Goal

Upgrade Paper Distill's wiki maintenance layer from "queued suggestions plus manual markdown writes" into a controlled, idempotent maintenance system that:

- safely patches managed wiki sections without overwriting user-authored notes
- executes confirmed maintenance tasks (`merge`, `promote`, `refresh`) through deterministic controllers
- propagates concept/topic version changes through an explicit dependency graph
- enriches Compile IR with stronger ideation-oriented tension fields
- generates higher-value trigger candidates for topic refresh and Idea generation

The end state should be a knowledge system that is both governance-friendly and materially better at producing research ideas.

## Non-Goals

- replacing Obsidian markdown as the final user-facing knowledge asset
- turning SQLite into the sole source of truth for all knowledge content
- introducing a graph database or external workflow service
- building a distributed job queue
- implementing a full autonomous research agent

## Current State

Phase 1 and Phase 2 have already landed the following:

- SQLite authority/index layers in `server/database.py`
- concept registry + merge history in `server/concept_registry.py`
- maintenance queue in `server/maintenance.py`
- Compile IR persistence, Resolve, and Write entrypoints in `server/compile_ir.py`
- IR-backed tension aggregation in `server/vault_lint.py`
- compile-aware MCP tools in `server/server.py`

The main remaining gaps are:

1. `commit_compile_result()` still overwrites whole files and does not preserve user-authored sections.
2. queue tasks can be confirmed, but there are no execution controllers for merge/promote/refresh.
3. `compile_deps` exists, but no invalidation/rebuild propagation uses it yet.
4. IR schema still lacks several fields needed for stronger ideation (`failure_modes`, `transfer_constraints`, `benchmark_scope`, `claimed_novelty`).
5. high-value trigger candidates (contradictions, recurring limitation spikes, cross-cluster bridges, evaluation splits) are not generated yet.

## Design Principles

### 1. Markdown Remains the User Asset

Wiki markdown remains the final knowledge artifact. SQLite is a control plane for orchestration, dependency tracking, and operation history — not a replacement wiki.

### 2. Managed vs User Sections Must Be Explicit

System-written sections must be isolated into explicit managed blocks. User-authored sections such as `## My Notes` must live outside those blocks and never be silently overwritten.

### 3. Maintenance Execution Must Be Idempotent

Controllers should behave like reconcile loops:

- safe to run repeatedly
- converge toward desired state
- no duplicate side effects on repeated runs

### 4. Dependency Propagation Must Be Explicit

Refresh scope must be derived from `compile_deps`, not inferred ad hoc from prose. If a concept version changes, the system should know exactly which pages depend on it.

### 5. Ideation Signals Must Be First-Class

Compile IR should not stop at summary-style fields. It must preserve research tension signals with evidence pointers so downstream idea generation can reason over them without re-extracting from prose.

## Target Architecture

## 1. Safe Write Kernel

`server/compile_ir.py::commit_compile_result()` becomes a patch engine rather than a whole-file writer.

### Page Model

Each generated page is partitioned into:

- managed blocks: fully system-owned sections
- user blocks: never overwritten by maintenance controllers

Managed blocks are delimited by stable markers:

```md
<!-- managed:start section=context -->
...
<!-- managed:end section=context -->
```

User blocks are unmarked or explicitly preserved sections such as:

- `## My Notes`
- `## Reading Notes`
- any section under a future `<!-- user:start --> ... <!-- user:end -->` contract

### Write Behavior

When writing an updated page:

1. Parse the existing page into managed and user blocks.
2. Compute current managed content hashes per section.
3. Compare them with the last committed managed hashes in `compile_state`.
4. If a managed block is unchanged since last compile, replace it directly.
5. If a managed block diverged:
   - attempt structured patch if the same block identity still exists
   - if patch cannot be applied safely, emit `conflict_detected`
6. Preserve all user blocks verbatim.

This allows the system to evolve generated content while protecting human-authored material.

## 2. Maintenance Controller

`server/maintenance.py` gains three execution controllers:

- `execute_merge(task_id)`
- `execute_promote(task_id)`
- `execute_refresh(task_id)`

### Queue State Model

The task status model expands to:

- `pending`
- `confirmed`
- `processing`
- `blocked`
- `done`
- `rejected`
- `failed`

Why:

- `blocked` represents "cannot safely proceed because page conflicts or prerequisites are unmet"
- `failed` represents execution errors that need debugging or retry

### Idempotency Rules

Each controller must be safe to re-run:

- merge of an already-merged concept returns a no-op result
- promoting an already-promoted concept returns a no-op result
- refresh of an already up-to-date page updates no state

## 3. Dependency Graph and Invalidation

`compile_deps` becomes the canonical propagation graph for refresh scope.

It must support dependencies for:

- paper pages
- concept pages
- method pages
- topic pages

### Version Rules

- alias addition: no version bump
- canonical name semantic change: bump version
- concept merge: target concept version bump
- concept promotion to topic: bump version and change type
- topic refresh: page compile version changes, but upstream concept versions do not bump unless semantics changed

### Propagation Model

When a concept/topic version changes:

1. query `compile_deps` for dependent pages
2. create a bounded refresh set
3. refresh each page once per run
4. if a refreshed page changes dependencies, enqueue further affected pages

Each reconciliation run receives a `run_id` so repeated selection in the same propagation wave is prevented.

## 4. IR Schema Expansion

Extend Compile IR with additional ideation-oriented fields:

- `failure_modes`
- `transfer_constraints`
- `benchmark_scope`
- `claimed_novelty`

Standardize tension entries to a richer shape:

```json
{
  "claim": "...",
  "source_ref": "...",
  "section": "...",
  "confidence": 0.0
}
```

This shape should be supported for:

- limitations
- assumptions
- negative_results
- failure_modes
- transfer_constraints
- open_questions where evidence exists

## 5. Trigger Candidate Layer

High-value triggers are generated in two stages:

### Candidate Generation

Deterministic or mostly deterministic pre-filtering produces candidates for:

- contradiction candidates
- recurring limitation spikes
- cross-cluster bridges
- benchmark evaluation splits

### Adjudication

LLM adjudication only runs on bounded candidate sets and decides:

- whether the candidate is valid
- what evidence supports it
- which topics/pages are affected
- whether it should trigger refresh or remain ideation-only signal

### Routing Rule

Not every trigger becomes a maintenance task.

- maintenance-worthy triggers become `stale_topic_refresh` or related queue tasks
- ideation-only triggers remain queryable signals for the idea-generator

## Data Model Changes

## `compile_state`

Add or evolve fields to support safe patching:

- `page_id`
- `page_type`
- `compile_version`
- `schema_version`
- `compiled_at`
- `ir_path`
- `content_hash`
- `managed_hashes_json` (new)
- `last_run_id` (optional)

`managed_hashes_json` stores per-block hashes so conflict detection can happen at section granularity instead of whole-page granularity.

## `maintenance_queue`

Expand allowed status values to include:

- `blocked`
- `failed`

Payloads for execution tasks should contain stable identifiers rather than derived file paths whenever possible.

## Trigger Signal Results

High-value ideation triggers do not need a dedicated authority table yet. They can be surfaced via:

- `query_tension_signals()`
- `analyze_knowledge_graph_sync()`
- a new Phase 3 MCP tool that returns trigger candidates directly

Only if trigger adjudication state needs persistence should a dedicated table be introduced later.

## External Experience Applied

The design borrows these ideas:

- Kubernetes/Kubebuilder controllers: reconcile desired state through idempotent loops
- Bazel explicit dependency graphs: refresh scope must come from declared deps, not fuzzy scans
- generated code guardrails: managed sections are machine-owned and clearly delimited
- SQLite WAL: many readers, one writer, explicit authority/history layers

## Testing Strategy

Phase 3 requires four new regression families:

### Safe Write Tests

- preserves `## My Notes`
- replaces unchanged managed blocks
- detects modified managed blocks
- emits `conflict_detected` instead of overwriting
- supports structured patch when block identity still matches

### Controller Idempotency Tests

- running merge twice is safe
- running promote twice is safe
- running refresh twice is safe

### Propagation Tests

- concept version bump refreshes dependent paper/concept/topic pages
- unrelated pages are not touched

### Trigger Tests

- recurring limitation spikes are generated from IR
- cross-cluster bridges are detected from deps
- contradiction candidates are emitted from topic/page evidence comparisons
- benchmark evaluation splits are surfaced when evaluation vocab diverges

## Rollout Strategy

Implement Phase 3 in this order:

1. safe write kernel and conflict detection
2. maintenance controller execution APIs
3. dependency propagation
4. IR schema expansion
5. trigger candidate generation
6. LLM adjudication integration
7. skill updates

This preserves the already-working Phase 1/2 foundations and adds the most safety-critical capabilities first.
