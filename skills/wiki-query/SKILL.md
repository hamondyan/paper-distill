---
name: wiki-query
description: Use when the user asks research questions, says "based on my papers", "what do I know about", "tell me about", "explain", "compare", "what papers discuss X", "在我的知识库中", "我的知识库里有没有", "帮我综述", "/query", or wants to synthesize knowledge from their approved paper collection.
---

# Wiki Query

Answer research questions by navigating and synthesizing from the wiki. Treat substantive answers as assets that grow the knowledge base, not disposable chat output.

## Workflow

### Step 1: Understand the Question

Categorize:
- **Factual**: "What is diffusion policy?" → concept article
- **Comparative**: "Compare VLA architectures" → method articles
- **Landscape**: "Trends in robot manipulation?" → topic article
- **Cross-cutting**: "Which papers use transformers for manipulation?" → search across papers
- **Gap analysis**: "What's missing in my knowledge base?" → wiki coverage analysis

### Step 2: Navigate the Wiki

1. Call `query-library(section="...")` to find relevant articles — **never read `_index.md` files** (they contain Dataview syntax, not data)
2. Read relevant wiki articles based on question type:
   - `wiki/concepts/{concept}.md` for factual
   - `wiki/methods/{method}.md` for comparative
   - `wiki/topics/{topic}.md` for landscape
   - Multiple `wiki/papers/` for cross-cutting
3. Follow `[[backlinks]]` to gather connected knowledge
4. If wiki lacks coverage: check approved `sources/notes/` for uncompiled evidence
5. Treat `inbox/` as pending evidence only if the user explicitly asks

### Step 3: Synthesize Answer

- Reference specific papers: `[[wiki/papers/{citekey}|{short title}]]`
- Reference concepts: `[[wiki/concepts/{concept}]]`
- Be explicit about gaps: "Your wiki has 5 papers on VLA but none on X"
- Never fabricate wiki content

### Step 4: Save Result (default for substantive answers)

If substantive (not a simple lookup), save to `insights/queries/{slug}.md` using the query-asset protocol:

```yaml
type: query-note | comparison-note | topic-synthesis | contradiction-note
title: "{short asset title}"
question: "{original question}"
date: {YYYY-MM-DD}
source_pages: [paths read during synthesis]
papers_referenced: [{citekeys}]
concepts_referenced: [{concepts}]
topics_referenced: [{topics}]
derived_actions: [{follow-up suggestions}]
promotion_targets:
  - page_type: topic | concept | method | paper
    page_id: "{target id}"
status: saved
```

Comparative answers should usually become `comparison-note`.
Landscape syntheses should usually become `topic-synthesis`.
Contradiction or tension-focused answers should usually become `contradiction-note`.

### Step 5: Suggest Follow-ups

If gaps found:
- "You might want to search for papers on X"
- "3 raw papers mention this but aren't compiled yet — run /compile"
- "This note should probably promote into `wiki/topics/{topic}`"

## Rules

- **Approved evidence first.** Prefer `sources/` + `wiki/`; inbox is pending, not established knowledge.
- **Knowledge compounds.** Saved queries become part of the wiki for future reference and future promotion into canonical pages.
- **Show impact.** Report what this query created, what it linked, and what it suggests updating.
