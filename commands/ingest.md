---
name: ingest
description: Use when the user wants to capture one or more resolved arXiv URLs, arXiv IDs, or arXiv DOI values. Writes raw evidence to raw/evidence/.
argument-hint: "[arxiv-url | arxiv-id | arxiv-doi]"
user-invocable: true
---

Use the v3 `ingest_and_read` tool to capture raw evidence.

The MCP call should receive one or multiple resolved arXiv URLs, arXiv IDs, or arXiv DOI values and capture those papers into `raw/evidence/`. For natural paper names, the agent resolves them first, then calls this command with the resolved arXiv identity.

Examples:
- `/ingest https://arxiv.org/abs/2410.24164`
- `/ingest 10.48550/arxiv.2410.24164`
- `/ingest 1706.03762`
- `/ingest 10.48550/arxiv.2410.24164, 1706.03762` - multiple resolved arXiv inputs captured in one batch

After write-heavy work, QMD refresh is a separate follow-up step rather than an implicit part of this command. Recommend `qmd update` after the current write round, and `qmd embed -f` if semantic retrieval must reflect the new state immediately.

When direct intake contains mixed items, report resolved arXiv inputs separately from unresolved user references so the user can see which items will be captured and which names need another lookup.
