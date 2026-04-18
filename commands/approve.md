---
name: approve
description: Mark inbox candidates approved from chat or explicit selection
user_invocable: true
---

Use the v3 `approve_papers` tool to add a plain `#approved` marker to matching inbox notes.

This command marks approval only. It does not capture raw evidence. After approval, use `/ingest approved` when you are ready to ingest the approved inbox notes.

The agent should pass exact identifiers from the current recommendation context whenever possible:
- paper IDs such as `arxiv:1706.03762`
- arXiv IDs such as `1706.03762`
- inbox note paths returned by `/discover`
- exact paper titles
- `all` when the user clearly approves every pending inbox candidate

Examples:
- `/approve arxiv:1706.03762`
- `/approve 1706.03762, 2410.24164`
- `/approve /absolute/path/to/vault/inbox/example.md`
- `/approve all`

If a user approves papers conversationally after recommendations, resolve their selection to the recommended paper IDs or inbox paths, then call `approve_papers`. Report which notes were approved and remind the user that `/ingest approved` performs capture.
