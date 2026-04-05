---
name: knowledge-query
description: Use when the user asks research questions, says "based on my papers", "what do I know about", "tell me about", "explain", "compare", "what papers discuss X", "在我的知识库中", "我的知识库里有没有", "帮我综述", "/query", or wants to synthesize knowledge from their approved paper collection.
---

# Knowledge Query

Answer research questions by navigating and synthesizing from the wiki. Save valuable results back to compound knowledge.

## Workflow

### Step 1: Understand the Question

Categorize:
- **Factual**: "What is diffusion policy?" → concept article
- **Comparative**: "Compare VLA architectures" → method articles
- **Landscape**: "Trends in robot manipulation?" → topic article
- **Cross-cutting**: "Which papers use transformers for manipulation?" → search across papers
- **Gap analysis**: "What's missing in my knowledge base?" → wiki coverage analysis

### Step 2: Navigate the Wiki

1. Call `query_vault(section="...")` to find relevant articles — **never read `_index.md` files** (they contain Dataview syntax, not data)
2. Read relevant wiki articles based on question type:
   - `wiki/concepts/{concept}.md` for factual
   - `wiki/methods/{method}.md` for comparative
   - `wiki/topics/{topic}.md` for landscape
   - Multiple `wiki/papers/` for cross-cutting
3. Follow `[[backlinks]]` to gather connected knowledge
4. If wiki lacks coverage: check approved `raw/notes/` for uncompiled evidence
5. Treat `inbox/` as pending evidence only if the user explicitly asks

### Step 3: Synthesize Answer

- Reference specific papers: `[[wiki/papers/{citekey}|{short title}]]`
- Reference concepts: `[[wiki/concepts/{concept}]]`
- Be explicit about gaps: "Your wiki has 5 papers on VLA but none on X"
- Never fabricate wiki content

### Step 4: Save Result (if valuable)

If substantive (not a simple lookup), save to `queries/{slug}.md`:

```yaml
question: "{original question}"
date: {YYYY-MM-DD}
papers_referenced: [{citekeys}]
concepts_referenced: [{concepts}]
```

### Step 5: Suggest Follow-ups

If gaps found:
- "You might want to search for papers on X"
- "3 raw papers mention this but aren't compiled yet — run /compile"

## Rules

- **Approved evidence first.** Prefer `raw/` + `wiki/`; inbox is pending, not established knowledge.
- **Knowledge compounds.** Saved queries become part of the wiki for future reference.
