---
name: wiki-compile
description: Use when the user says "compile", "update wiki", "编译wiki", "create wiki article", "turn notes into wiki", "把笔记写入wiki", "/compile", or wants to create or update structured wiki articles from approved raw papers. Also trigger after `paper-add` or `process-inbox` completes if the user asks to compile immediately.
---

# Wiki Compile

Compile approved raw papers into structured wiki knowledge. You are the sole writer of wiki/, and your job is to keep it useful as a thinking interface rather than a static archive.

## Two Modes

### Lightweight Mode (auto after ingest)

1. Update `_index.md` files to reflect new raw papers
2. Scan abstracts for key concepts
3. Add `[[backlinks]]` from new papers to existing concepts
4. Create concept stubs **only if referenced by ≥2 papers** — leave single-reference concepts as unresolved `[[dead links]]` (Obsidian handles this gracefully)

### Deep Mode (manual /compile)

All lightweight tasks, plus:
1. Create/update `wiki/papers/{citekey}.md`
2. Create/update `wiki/concepts/{concept}.md`
3. Create/update `wiki/methods/{method}.md`
4. Update `wiki/topics/{topic}.md`
5. Rebuild all `_index.md` files

## Deep Compile Workflow

### Step 1: Find Uncompiled Papers

Call `query_vault(section="raw_notes", uncompiled_only=true)`.

### Step 2: Compile Each Paper

Read `raw/notes/{date}/{citekey}.md` and consult `raw/source/{date}/{citekey}.md` as needed. Create `wiki/papers/{citekey}.md` following the structure in `templates/wiki-paper.md.j2`.

When reading `raw/source`, assume it is inline evidence markdown:
- figures, tables, and equations are usually rendered near the surrounding section text rather than in trailing snapshot sections
- use the `.assets.json` sidecar when you need the authoritative structured figure/table/equation payload

Required frontmatter: citekey, paper_id, title, authors, year, doi, arxiv_id, venue, topics, concepts, methods, claims, limitations, open_questions, source_raw_path, source_note_path, zotero_uri, compiled, quality_score, relevance_score, confidence, updated_at.

Key requirements:
- Every paper must link to both raw layers: `[[raw/notes/...]]` and `[[raw/source/...]]`
- Every paper must link to ≥2 concept articles
- "Why read this" must be 1 sentence
- "Insights for My Research" must reference `settings.json → research_profile.direction`

After creating the wiki note, set `compiled: true` in the raw paper's frontmatter.

### Step 3: Update Concept Articles

Follow `templates/wiki-concept.md.j2` structure.

- **Existing concept:** Add new paper to "Representative Papers", update paper_count, and refresh `Boundary Cases`, `Nearby Concepts`, or `Unresolved Ambiguity` when the new evidence changes them
- **New concept (referenced by ≥2 papers):** Create article with canonical definition, key ideas, representative papers, nearby concepts, and unresolved ambiguity notes

### Step 4: Update Method Articles

If multiple papers describe competing methods for the same task, create/update `wiki/methods/{method}.md` following `templates/wiki-method.md.j2`.

### Step 5: Update Topic Landscapes

Create/update `wiki/topics/{topic}.md` with the thinking-surface structure:
- `Established Understanding`
- `Recent Developments`
- `Open Tensions`
- `Next Questions`

Use `templates/wiki-topic.md.j2` for the target shape.

### Step 6: Ensure Index Integrity

Index files use **Obsidian Dataview** queries from YAML frontmatter. Your main job is ensuring frontmatter quality — if frontmatter is correct, Dataview handles the rest. Use `query_vault` for AI reads, NOT `_index.md` parsing.

## Backlink Rules

- wiki/papers/ → both raw layers (`[[raw/notes/...]]` and `[[raw/source/...]]`)
- wiki/papers/ → relevant concepts (`[[concepts/{concept}]]`)
- concepts → papers that discuss them
- methods → papers and concepts compared
- topics → key concepts and papers

## EDC Compile Protocol (Extract → Resolve → Write)

For structured compilation with registry integration, use the three-stage EDC protocol.

### Stage 1: Extract (Agent + LLM)

For each uncompiled paper:
1. Read raw notes and source PDF
2. Produce a structured IR dict with required fields:
   - `citekey`, `title`, `authors`, `candidate_concepts`, `tension_fields`
   - `tension_fields` must include: `limitations`, `assumptions`, `open_questions`, `negative_results`
   - Prefer also populating: `failure_modes`, `transfer_constraints`, `benchmark_scope`, `claimed_novelty`
3. Submit to `write_compile_ir(citekey, ir_json)` — validates schema and persists to `compiled_ir/{citekey}.json`

### Stage 2: Resolve (Pure Python)

Call `resolve_compile_ir(citekeys)` — no LLM needed.
- Maps each `candidate_concept` to its canonical registry entry
- Registers new concepts automatically (or auto-merges slug/abbreviation/spelling variants)
- Writes `compiled_ir/{citekey}_resolved.json`

### Stage 3: Write (Agent)

Before writing, check `get_maintenance_queue(status="confirmed")`.

- If execution controllers are available, consume confirmed `merge_candidate`, `promote_to_topic`, and `stale_topic_refresh` tasks via `execute_maintenance_task(task_id)`.
- If a confirmed task has no execution controller yet, surface it before writing and proceed conservatively.

For each paper:
1. Render wiki markdown from resolved IR
2. Call `commit_compile_result(page_id, page_type, content, frontmatter, ir_path, deps)`
   - This is the sole write exit — records compile_state and deps in SQLite
   - Wraps managed sections with `<!-- managed:start section=... -->` / `<!-- managed:end section=... -->` markers
   - `## My Notes` sections are **never** inside managed markers — always preserved
   - If a managed block was manually edited and cannot be safely patched, the write returns `conflict_detected` instead of silently overwriting
   - Report the resulting knowledge impact panel: created pages, updated pages, linked pages, topic refreshes, and conflicts

### Subagent Usage (>3 papers)

For >3 papers, dispatch parallel Extract subagents (1-3 papers each). Each returns IR dicts.
Main agent runs batch Resolve, then sequential Write.

### Concept Registry Rules

- Always call `resolve_concept(surface_form)` before creating a new concept article
- If resolved: link to existing; if not: the Resolve stage will register it
- After Write stage: call `register_concept` for any hand-crafted aliases
- Promotion candidates (concept referenced by ≥5 papers): note for `reconcile_maintenance`
- High-value query assets and idea memos should be treated as supporting evidence when they clarify tensions, but canonical pages remain controlled by compile and maintenance decisions
