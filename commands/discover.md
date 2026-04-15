---
name: discover
description: Discover candidate papers and write inbox stubs
user_invocable: true
---

Run the v3 discovery flow using the `paper-distill:paper-intake` skill.

This searches paper sources, deduplicates against `.state/seen_papers.json`, writes new inbox stubs into `inbox/`, and reports how many papers were saved versus skipped because they were already seen.
