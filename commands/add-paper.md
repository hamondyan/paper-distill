---
name: add-paper
description: Directly add a user-confirmed paper into the knowledge vault
user_invocable: true
---

Directly add a specific user-confirmed paper into the approved knowledge base using the `paper-distill:paper-add` skill.

The argument can be a DOI, arXiv ID, paper URL, or PDF URL. Examples:
- `/add-paper 10.48550/arxiv.2410.24164`
- `/add-paper arxiv:2410.24164`
- `/add-paper https://arxiv.org/abs/2410.24164`

This skips `inbox/`, lets the knowledge maintainer write approved raw layers directly, performs Zotero handoff, and prepares the paper for wiki compilation.
