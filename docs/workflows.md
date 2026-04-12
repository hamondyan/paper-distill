# Workflows

## Discovery To Library

```text
source-discover -> inbox review -> source-ingest -> sources/evidence -> wiki/papers
```

1. Run `/discover` or `/digest`.
2. Review generated notes in `Paper Distill/inbox/`.
3. Set `status: approved` for papers you want to keep.
4. Run `/process-inbox`.
5. Paper Distill captures evidence and creates or refreshes the canonical paper page.

## Direct Add

```text
add-paper -> sources/evidence -> wiki/papers
```

Use this when you already trust a paper enough to add it.

```text
/add-paper 10.48550/arxiv.2410.24164
```

The tool resolves metadata, captures source evidence, creates the wiki paper page, and performs Zotero handoff if enabled.

## Compile

The EDC pipeline (Extract → Resolve → Write) refreshes wiki pages from evidence and hidden IR.

```text
sources/evidence/{date}/{citekey}.md
  │
  ▼  (agent reads evidence, builds IR)
paper-distill-extract(citekey, ir_json)
  │ writes
  ▼
.state/ir/{citekey}.json
  │
  ▼  (pure Python, no LLM)
knowledge-compile-resolve([citekeys])
  │ writes
  ▼
.state/ir/{citekey}_resolved.json
  │
  ▼  (agent writes compiled markdown)
knowledge-compile-publish(page_id, page_type, content, frontmatter, ir_path, deps)
  │
  ▼
wiki/papers/{citekey}.md
```

Manual notes (sections like `## My Notes`) are detected before the Write step and appended after generated content. If `knowledge-compile-publish` returns `manual_edit_conflict: true`, the write is aborted and the user is notified.

See [Compile IR Schema](compile-ir-schema.md) for the full IR field reference.

## Query

Use `/query` for research questions over the maintained vault.

Substantive answers should be saved under:

```text
Paper Distill/insights/queries/
```

Saved query notes can reference papers, concepts, topics, and promotion targets.

## Ideas

Use `/ideas` to find research opportunities from local graph tension.

Idea notes live under:

```text
Paper Distill/insights/ideas/
```

Each idea note carries its own state, evidence, kill criteria, next step, and decision reason. The idea note itself is the only default visible asset for this workflow.

## Memory

Memory is for stable preferences, long-term constraints, and important decisions. It is no longer the default lifecycle sink for ordinary research ideas.

Memory views live under:

```text
Paper Distill/memory/
```

Machine state for memory events lives under:

```text
Paper Distill/.state/memory/
```
