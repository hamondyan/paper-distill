---
name: paper-summarize
description: Use when the user says "summarize this paper", "总结这篇论文", "/summarize", or wants a quick structured summary without full wiki compilation.
---

# Paper Summarize

Quick structured summary of a paper for assessment before deciding whether to ingest.

## Workflow

### Step 1: Get Paper Content

- **DOI provided:** Call `resolve_metadata` for title/authors/abstract/venue. If abstract is sufficient, proceed.
- **URL or arXiv ID:** Call `fetch_pdf_text` — it automatically uses ar5iv HTML (faster, cleaner, better token density) for arXiv papers, falling back to PDF only if ar5iv fails.
- **Abstract/text pasted:** Work with what's given.

### Step 2: Generate Summary

Read `settings.json → research_profile.direction` for context. Output:

```markdown
## {Paper Title}

**{Authors}** ({Year}) | {Venue}

### Motivation
{Why this problem matters — 1-2 sentences}

### Approach
{Core technical method — 2-3 sentences}

### Key Findings
- {Finding 1}
- {Finding 2}

### Strengths
- {What's good}

### Limitations
- {What's missing}

### Relevance to Your Research
{Specific connection to research_profile.direction}
```

### Step 3: Offer Next Actions

- "Add to knowledge vault now?" → triggers `paper-add`
- "Compile into wiki?" → triggers `wiki-compile`
- "Search for related papers?" → triggers `paper-discover`

## Rules

- Be precise — do not hallucinate results or methods
- If abstract only, say: "Based on abstract only — full text not available"
- Relevance section must reference the user's actual research direction
