---
name: discover
description: Discover candidate papers and write inbox stubs
user_invocable: true
---

Call `discover_papers` to run the v3 discovery flow.

This searches paper sources, deduplicates against `.state/seen_papers.json`, writes new inbox stubs into `inbox/`, and reports how many papers were saved versus skipped because they were already seen.
Do not ingest from this command. After discovery, the next step is human approval in the inbox.
