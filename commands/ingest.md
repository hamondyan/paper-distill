---
name: ingest
description: Manually approve and ingest a paper by DOI or URL
user_invocable: true
---

Manually ingest a specific paper using the `paper-distill:paper-ingest` skill.

The argument can be a DOI, arXiv ID, or paper URL. Examples:
- `/ingest 10.48550/arxiv.2410.24164`
- `/ingest arxiv:2410.24164`
- `/ingest https://arxiv.org/abs/2410.24164`

The paper will be resolved, added to Zotero, written to raw/, and can then be compiled into the wiki.
