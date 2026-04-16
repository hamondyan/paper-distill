---
name: lint
description: Run v3 vault health checks
user_invocable: true
---

Run `lint_vault` and report dead links, malformed links, alias ambiguity, repeated links, template-like footer linking, and oversized frontmatter.
Do not rewrite files from this command.
If the user needs retrieval or index health after linting, route them to `docs/qmd-cli.md`.
