---
name: ingest
description: Ingest approved inbox items or agent-resolved arXiv identities
user_invocable: true
---

Use the v3 `ingest_and_read` tool to ingest raw evidence.

If the argument is `approved`, ingest inbox notes whose body contains a plain `#approved` marker.

Otherwise, the agent resolves user-provided paper references to arXiv identities first. The MCP call should receive one or multiple resolved arXiv URLs, arXiv IDs, or arXiv DOI values and capture those papers into `raw/evidence/`.

Examples:
- `/ingest approved`
- `/ingest https://arxiv.org/abs/2410.24164`
- `/ingest 10.48550/arxiv.2410.24164`
- `/ingest 1706.03762`
- `/ingest openvla, octo, diffusion policy` — agent resolves these names to multiple resolved arXiv identities, then calls `ingest_and_read` once

After write-heavy work, QMD refresh is a separate follow-up step rather than an implicit part of this command. Recommend `qmd update` after the current write round, and `qmd embed -f` if semantic retrieval must reflect the new state immediately.
