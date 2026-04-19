---
name: lint
description: Use when the user wants to audit the vault for dead links, alias issues, schema problems, concept/link coverage, or orphaned concept pages. Reports issues; does not rewrite files.
user-invocable: true
---

Run `lint_vault` and report dead links, malformed links, alias ambiguity, repeated links, template-like footer linking, oversized frontmatter, paper pages missing concept links, paper key concepts not linked in the body, overly dense paper concept links, decorative concept links, and concept pages without supporting papers.
Do not rewrite files from this command.
If the user needs retrieval or index health after linting, route them to `docs/qmd-cli.md`.
