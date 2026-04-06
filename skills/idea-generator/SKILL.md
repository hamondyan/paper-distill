---
name: idea-generator
description: Use when the user says "research ideas", "gap analysis", "给我一些研究思路", "研究方向", "有什么可以做的", "open problems", "what should I work on", "what are the research gaps", "帮我找研究方向", "/ideas", or asks for novel angles and directions based on their paper collection.
---

# Idea Generator

Identify research gaps and generate actionable ideas. Uses `analyze_knowledge_graph` MCP tool for structural analysis, then LLM for qualitative interpretation.

## Workflow

### Step 1: Structural Analysis (Python)

Call `analyze_knowledge_graph` MCP tool. It returns condensed gap lists from two sources:

**Graph-based (always available):**
- **Methodology mismatches:** Concepts proven in domain A but not applied to user's topics
- **Combination opportunities:** Concept pairs in the same topic that never appear in the same paper
- **Recurring problems:** Limitations/open questions mentioned across multiple papers
- **Scaling questions:** Results limited to small-scale or toy settings

**IR-based (when compiled_ir/ exists):**
- **ir_recurring_limitations:** Structured limitation claims from ≥2 papers (higher precision than text scan)
- **ir_open_question_clusters:** Open questions grouped by keyword theme
- **ir_negative_results:** Explicit null/negative results from paper IRs

For deeper tension analysis, also call `query_tension_signals(min_occurrence=2)` — this returns the full `all_assumptions` list that the LLM can scan for conflicting premises across papers.

### Step 2: Qualitative Interpretation (LLM)

1. Read `settings.json → paper_distill.research_profile` for context
2. For each gap from Step 1, read 2-3 referenced papers/concepts to understand the specifics
3. Generate structured idea cards:

```markdown
### Idea {N}: {Title}

**Gap type:** {methodology_mismatch | combination | recurring_problem | scaling}
**Description:** {2-3 sentences}
**Local Evidence:**
- [[wiki/papers/{citekey}]] — {relevance}
- [[wiki/concepts/{concept}]] — {relevance}
**Assumptions:** {What implicit assumptions does the source method rely on?}
**Conflict:** {Where do these assumptions clash with the target domain?}
**Bridge:** {What new technique or adaptation is needed to resolve the conflict?}
**Kill Criteria:** {Under what conditions is this idea infeasible or already solved?}
**Feasibility:** {Low/Medium/High}
**Novelty:** {Low/Medium/High}
**Priority:** {novelty × feasibility}
```

### Step 3: Save Results

Write to `queries/idea-analysis-{YYYY-MM-DD}.md` with frontmatter:
```yaml
type: idea-analysis
date: {today}
topics_analyzed: [{topics}]
gaps_found: {count}
```

## Output

Present **top 5 ideas** ranked by priority. Then offer:
- "Want me to search for papers related to any of these ideas?"
- "Shall I save the full analysis to the wiki?"
