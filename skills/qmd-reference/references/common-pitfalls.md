# Common Pitfalls

Every entry is a mistake that has cost real time. Read this before deciding the index is broken.

## "I wrote the page but search can't find it"

Almost always `qmd update` was skipped. Business MCP writes Markdown; it does not refresh the index. Run `qmd update`, then retry the query. If the user needs semantic retrieval (not just lexical), also run `qmd embed -f`.

## Collection name typos

Collection handles are fixed strings, not free-form tags. The correct set is:

- `canon-papers`
- `canon-concepts`
- `insights-conversations`
- `insights-ideas`
- `raw-evidence`

Common typos: `papers` (missing `canon-`), `concepts`, `conversation-insights` (order swapped), `raw` (missing `-evidence`). A typo returns zero results silently — easy to misread as "nothing in the vault". Run `qmd collection list` to double-check before concluding that a layer is empty.

## Mixing plain and typed query lines

```bash
# WRONG — produces confusing results
qmd query $'diffusion policy\nvec: transformer'
```

A query is either fully plain (one line) or fully typed (every line prefixed with `lex:`, `vec:`, or `hyde:`). Mixing the two modes silently falls back to parsing the whole thing as a plain string, so the typed directives are ignored.

## Reaching for `qmd search` / `qmd vsearch` first

`qmd query` is hybrid and reranks — it is the right default. The single-mode commands are diagnostic tools for when hybrid is visibly mis-ranking. Starting with them wastes a turn.

## Forgetting the vault path when repairing collections

`qmd collection add --name canon-papers` without a path argument will fail or add the wrong directory. Always pass the absolute vault subpath:

```bash
qmd collection add /absolute/path/to/vault/wiki/papers --name canon-papers
```

## Assuming `qmd get` needs a collection prefix

```bash
# WRONG
qmd get canon-papers/openvla.md
# RIGHT
qmd get wiki/papers/openvla.md
```

`qmd get` takes a repo-relative file path, not a collection handle. Collection handles are a `qmd query -c` / `qmd ls` concept.

## Trusting stale `qmd status` output

If the user has been running business MCP writes in parallel, `qmd status` from earlier in the turn is already stale. Re-run it when the question "is the index current?" actually matters.
