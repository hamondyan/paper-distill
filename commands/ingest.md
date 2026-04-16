---
name: ingest
description: Ingest approved inbox items or a direct arXiv URL / DOI
user_invocable: true
---

Use the v3 `ingest_and_read` tool to ingest raw evidence.

If the argument is `approved`, ingest inbox notes whose body contains a plain `#approved` marker.
Otherwise treat the argument as a direct arXiv URL or arXiv DOI and capture that one paper into `raw/evidence/`.

Examples:
- `/ingest approved`
- `/ingest https://arxiv.org/abs/2410.24164`
- `/ingest 10.48550/arxiv.2410.24164`

After write-heavy work, QMD refresh is a separate follow-up step rather than an implicit part of this command. Recommend `qmd update` after the current write round, and `qmd embed -f` if semantic retrieval must reflect the new state immediately.
