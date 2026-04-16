# QMD CLI In Paper Distill

QMD CLI is the primary source; command details follow the runtime output of `qmd --help`.

Use this document for the Paper Distill mapping, then verify uncertain syntax with runtime help.

## Paper Distill Main Path

This is the normal read/index path in this repo:

```text
discover/approve/ingest with Paper Distill -> read with qmd query/get -> write with business MCP -> refresh with qmd update and qmd embed -f when needed
```

Paper Distill business MCP is for:

- `discover_papers`
- `ingest_and_read`
- `upsert_wiki_page`
- `check_concept_alias`
- `merge_concept`
- `lint_vault`

QMD CLI is for:

- `qmd query`
- `qmd get`
- `qmd status`
- `qmd update`
- `qmd embed -f`
- `qmd collection ...`
- `qmd context ...`
- `qmd ls`

## Collections In This Repo

- `canon-papers` -> `wiki/papers`
- `canon-concepts` -> `wiki/concepts`
- `insights-conversations` -> `insights/conversations`
- `insights-ideas` -> `insights/ideas`
- `raw-evidence` -> `raw/evidence`

These names are the QMD-facing handles for the main Paper Distill knowledge layers.

## Core Patterns

### `qmd query`

Use `qmd query <query>` as the default retrieval path. Runtime `qmd --help` describes it as the recommended hybrid search with auto expansion and reranking.

Examples:

```bash
qmd query "diffusion scaling law"
qmd query $'lex: "transformer"\nvec: retrieval augmentation'
qmd query "paper distill concept merge" -c canon-concepts
```

Use `-c <collection>` when you want to stay within one repo layer such as `canon-papers`, `canon-concepts`, or `raw-evidence`.

### `qmd get`

Use `qmd get <file>[:line] [-l N]` when you already know the target file or want a line slice.

Examples:

```bash
qmd get wiki/papers/attention-is-all-you-need.md
qmd get wiki/concepts/retrieval-augmented-generation.md:1 -l 80
```

### `qmd status`

Use `qmd status` to inspect index and collection health before assuming the read/index path is healthy.

### `qmd update`

Use `qmd update` after a round of business writes when QMD’s index should catch up to the latest Markdown state.

### `qmd embed -f`

Use `qmd embed -f` when embeddings must be refreshed immediately after write-heavy work.

### `qmd collection ...`

Use collection commands to inspect or repair the five expected mounts.

Examples:

```bash
qmd collection list
qmd collection show canon-papers
qmd collection add <vault>/wiki/papers --name canon-papers
```

### `qmd context ...`

Use context commands to inspect or repair the human-written summaries attached to those collections.

Examples:

```bash
qmd context list
qmd context add qmd://canon-papers "Canonical distilled papers"
```

### `qmd ls`

Use `qmd ls` to inspect indexed files by collection or subpath.

Examples:

```bash
qmd ls
qmd ls canon-papers
qmd ls canon-concepts/retrieval
```

## Working Rhythm

1. Use Paper Distill MCP for business actions such as discovery, approved ingest, canonical page writes, concept merges, and linting.
2. Use `qmd query` and `qmd get` for reading.
3. Use `qmd status`, `qmd collection ...`, and `qmd context ...` for health checks.
4. After write-heavy work, run `qmd update`.
5. If semantic retrieval needs to reflect the new state immediately, run `qmd embed -f`.

## Optional Appendix

These are official QMD commands available in the local runtime, but they are not the normal Paper Distill path:

- `qmd search <query>` for BM25-only keywords
- `qmd vsearch <query>` for vector-only search
- `qmd multi-get <pattern>` for batch fetches
- `qmd cleanup` for cache cleanup
- `qmd mcp` for QMD’s own MCP server
- `qmd skill show/install` for the packaged QMD skill
- `qmd bench <fixture.json>` for search benchmarking
