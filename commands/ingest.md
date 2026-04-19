---
description: Use when the user wants to capture one or more resolved arXiv URLs, IDs, DOIs, or paper titles/acronyms. Writes raw evidence to raw/evidence/.
argument-hint: "[arxiv-url | arxiv-id | arxiv-doi | paper-title]"
---

Use the v3 `ingest_and_read` tool to capture raw evidence.

The agent resolves user-provided paper references to arXiv identities first. The MCP call should receive one or multiple resolved arXiv URLs, arXiv IDs, or arXiv DOI values and capture those papers into `raw/evidence/`. The MCP tool does not search arbitrary names by itself.

Examples:
- `/ingest https://arxiv.org/abs/2410.24164`
- `/ingest 10.48550/arxiv.2410.24164`
- `/ingest 1706.03762`
- `/ingest openvla, octo, diffusion policy` - agent resolves these names to multiple resolved arXiv identities, then calls `ingest_and_read` once

After write-heavy work, QMD refresh is a separate follow-up step rather than an implicit part of this command. Recommend `qmd update` after the current write round, and `qmd embed -f` if semantic retrieval must reflect the new state immediately.

When direct intake contains mixed items, report resolved arXiv inputs separately from unresolved user references so the user can see which items will be captured and which names need another lookup.
