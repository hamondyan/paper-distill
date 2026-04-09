---
name: source-discover
description: Use when the user says "search papers", "find papers about X", "搜索论文", "帮我找关于X的论文", "/discover", "/search", or provides a specific topic/keyword to search. This is for ad-hoc or topic-specific source discovery — for the full daily batch workflow, use `source-digest`.
---

# Source Discover

Search for academic papers, score them, bind the shortlist to arXiv, and stage detailed candidate cards in `inbox/`. Do not write directly to `sources/` from discovery.

## Workflow

1. Read `settings.json → paper_distill.research_profile`, `topics`, and `scoring`
2. Determine scope:
   - ad-hoc query if the user provides one
   - otherwise configured topics
3. Call `source-discover(..., save_to_inbox=true)`
   - only arXiv-bound candidates should survive this step
4. Present a concise summary of the best candidates
5. Tell the user to review the generated inbox notes in Obsidian by editing `status`

## Rules

- Discovery is a recommendation stage, not an approval stage
- Candidates without arXiv bindings do not enter the formal inbox
- Top venues and whitelist authors should boost ranking, but not override clear irrelevance
- Candidate cards should be detailed enough for human review without opening the PDF immediately
