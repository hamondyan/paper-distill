---
name: ingest
description: Ingest approved inbox items or a direct paper URL
user_invocable: true
---

Ingest raw evidence using the `paper-distill:paper-intake` skill in v3 mode.

If the argument is `approved`, ingest inbox notes whose body contains a plain `#approved` marker.
Otherwise treat the argument as a direct paper URL and capture that one paper into `raw/evidence/`.

Examples:
- `/ingest approved`
- `/ingest https://arxiv.org/abs/2410.24164`
