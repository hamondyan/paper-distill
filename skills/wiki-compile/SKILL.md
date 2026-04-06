---
name: wiki-compile
description: Use when the user says "compile", "update wiki", "编译wiki", "create wiki article", "turn notes into wiki", "把笔记写入wiki", "/compile", or wants to create or update structured wiki articles from approved raw papers. Also trigger after `paper-add` or `process-inbox` completes if the user asks to compile immediately.
---

# Wiki Compile

Compile approved raw papers into structured wiki knowledge. You are the sole writer of wiki/.

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

Required frontmatter: citekey, paper_id, title, authors, year, doi, arxiv_id, venue, topics, concepts, methods, claims, limitations, open_questions, source_raw_path, source_note_path, zotero_uri, compiled, quality_score, relevance_score, confidence, updated_at.

Key requirements:
- Every paper must link to both raw layers: `[[raw/notes/...]]` and `[[raw/source/...]]`
- Every paper must link to ≥2 concept articles
- "Why read this" must be 1 sentence
- "Insights for My Research" must reference `settings.json → research_profile.direction`

After creating the wiki note, set `compiled: true` in the raw paper's frontmatter.

### Step 3: Update Concept Articles

Follow `templates/wiki-concept.md.j2` structure.

- **Existing concept:** Add new paper to "Representative Papers", update paper_count
- **New concept (referenced by ≥2 papers):** Create article with definition, key ideas, representative papers, related concepts

### Step 4: Update Method Articles

If multiple papers describe competing methods for the same task, create/update `wiki/methods/{method}.md` following `templates/wiki-method.md.j2`.

### Step 5: Update Topic Landscapes

Create/update `wiki/topics/{topic}.md` with landscape overview, key papers, trends, open problems.

### Step 6: Ensure Index Integrity

Index files use **Obsidian Dataview** queries from YAML frontmatter. Your main job is ensuring frontmatter quality — if frontmatter is correct, Dataview handles the rest. Use `query_vault` for AI reads, NOT `_index.md` parsing.

## Backlink Rules

- wiki/papers/ → both raw layers (`[[raw/notes/...]]` and `[[raw/source/...]]`)
- wiki/papers/ → relevant concepts (`[[concepts/{concept}]]`)
- concepts → papers that discuss them
- methods → papers and concepts compared
- topics → key concepts and papers

## Subagent Usage (3-Phase Protocol)

For >3 uncompiled papers, use a Map→Reduce→Write protocol:

### Phase 1: Map (Parallel)
Dispatch parallel compilation subagents (each compiles 1-3 papers). Each subagent:
- Creates `wiki/papers/{citekey}.md` as usual
- Returns a list of **candidate concepts** (name, definition, source papers) instead of directly creating concept articles
- Uses `compiler-prompt.md` for subagent instructions

### Phase 2: Reduce (Main Agent)
Main agent collects all candidate concepts from all subagents and:
1. **Canonicalize names**: Merge "diffusion policy" and "Diffusion Policy" into one
2. **Deduplicate**: If two subagents propose the same concept, merge their paper lists
3. **Alias registration**: If concept already exists in vault under a different name, record as alias
4. **Threshold check**: Only create concept articles for concepts referenced by ≥2 papers

### Phase 3: Write (Main Agent)
After reconciliation:
1. Create/update concept articles with merged paper lists
2. Create/update method articles for competing approaches
3. Update topic landscapes and index files
4. Set `compiled: true` in all processed raw notes
