---
name: query
description: Ask a research question against your knowledge base
user_invocable: true
---

Answer a research question by navigating the wiki using the `paper-distill:knowledge-workbench` skill.

The argument is the question. Example: `/query what VLA architectures exist and how do they compare?`

The answer is synthesized from the maintained wiki. Substantive results are saved to `insights/queries/` as reusable knowledge assets and may propose controlled updates back into the wiki.
