# v3.0 Architecture

Markdown files are the only source of truth.
QMD CLI is the only read/index path.
Paper Distill business MCP owns deterministic writes, validation, and business workflows.

## Storage Layers

- `inbox/` holds discovery candidates for human approval.
- `raw/evidence/` holds captured source evidence.
- `wiki/papers/` holds agent-owned canonical paper pages.
- `wiki/concepts/` holds agent-owned canonical concept pages.
- `insights/ideas/` holds idea assets written through Python tools.
- `insights/conversations/` holds distilled conversation insights written through Python tools.
- `exports/presentations/` is the direct-written delivery area.
- `.state/` holds operational state such as the seen-paper cache.
- `vault-log.md` records vault actions.

## Read And Index Surface

- QMD CLI is the only read/index path.
- Use `qmd query` for normal retrieval, `qmd get` for direct document fetches, and `qmd ls` to inspect indexed files.
- Use `qmd status`, `qmd collection ...`, and `qmd context ...` to inspect collection and context health.
- Use `qmd update` and `qmd embed -f` as explicit follow-up steps after write-heavy work.
- Treat [qmd-cli.md](qmd-cli.md) as the repo guide and runtime `qmd --help` as the authority for command details.

## Business MCP Surface

- `discover_papers(query=None)` writes inbox stubs and updates `.state/seen_papers.json`.
- `approve_papers(input_value)` marks selected inbox stubs approved from chat or explicit paper IDs/paths.
- `ingest_and_read(input_value)` captures approved inbox notes or agent-resolved natural references and batch arXiv identities into `raw/evidence/`.
- `check_concept_alias(name)` checks concept names and aliases from `wiki/concepts/`.
- `upsert_wiki_page(page_type, target, frontmatter, body)` writes `paper`, `concept`, `idea`, or `conversation` pages through Python validation.
- `merge_concept(old, new)` rewrites concept links and adds the old surface as an alias on the target concept.
- `lint_vault()` reports dead links, malformed links, alias ambiguity, repeated links, template-like footer linking, oversized frontmatter, paper concept-link quality issues, and concept pages without supporting papers.
- Business MCP does not wrap `qmd query`, `qmd get`, `qmd status`, `qmd update`, or `qmd embed -f`.

## First-Release Flow

```text
discover -> approve in chat -> ingest -> qmd query/get -> canonical write -> lint
```

Approval is file-native. Only a plain `#approved` tag in the inbox note body allows approved-batch ingest, but users still approve through the agent and `approve_papers` writes that marker for them.

## Failure Semantics

- Missing or invalid `settings.json` returns an explicit configuration error.
- Missing or unavailable qmd blocks the QMD CLI read/index path until QMD is installed and configured.
- Raw evidence capture may rewrite an existing `raw/evidence/` file for the same paper ID as capture repair.
- If concept compounding fails during ingest, the paper still enters the vault and the failure is reported.
- Index refresh is a separate explicit QMD step after successful business writes.
