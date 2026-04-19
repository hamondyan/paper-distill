---
description: Use when the user wants to find new papers, pull a daily digest, or search arXiv/Semantic Scholar/OpenAlex for a research topic. Runs stateless v3 discovery and returns chat-only candidates.
argument-hint: "[query]"
---

Call `discover_papers` to run the v3 discovery flow.

This searches paper sources, scores and ranks candidates, and returns the results directly to the agent for presentation in chat. It does not write `inbox/`, update a seen cache, approve papers, or ingest anything.

After discovery, help the user choose candidates from the current chat result. To capture a paper, resolve the chosen item to an arXiv URL, arXiv ID, or arXiv DOI and call `/ingest` with that resolved identity.
