---
name: discover
description: Use when the user wants to find new papers, pull a daily digest, or search arXiv/Semantic Scholar/OpenAlex for a research topic. Runs the v3 discovery flow and writes deduplicated inbox stubs.
argument-hint: "[query]"
user-invocable: true
---

Call `discover_papers` to run the v3 discovery flow.

This searches paper sources, deduplicates against `.state/seen_papers.json`, writes new inbox stubs into `inbox/`, and reports how many papers were saved versus skipped because they were already seen.
Do not ingest from this command. After discovery, the next step is human approval in chat, with the agent resolving that selection and writing the internal approval marker.
