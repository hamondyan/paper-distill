---
name: search
description: Search the v3 knowledge base through qmd
user_invocable: true
---

Use `kb_search` with default scope `canon`.
Only widen to `insights` or `raw` when the user explicitly asks for those layers.
If qmd is unavailable, report `not_ready` instead of falling back to filesystem search.
