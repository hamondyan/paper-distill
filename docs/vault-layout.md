# Vault Layout

Paper Distill writes inside the configured vault root.

```text
<vault>/
├── inbox/
├── raw/
│   └── evidence/
├── wiki/
│   ├── papers/
│   └── concepts/
├── insights/
│   ├── ideas/
│   └── conversations/
├── exports/
│   └── presentations/
├── .state/
├── vault-log.md
└── settings.json
```

## User-Visible Layers

- `inbox/`: candidate papers awaiting body-level `#approved`.
- `raw/evidence/`: captured source Markdown for approved or direct ingests.
- `wiki/papers/`: canonical paper pages, written by agents through Python tools.
- `wiki/concepts/`: canonical concept pages for core concepts only.
- `insights/ideas/`: idea notes written through Python tools.
- `insights/conversations/`: distilled conversation insights written through Python tools.
- `exports/presentations/`: direct-written presentation deliverables.

## Operational State

- `.state/seen_papers.json`: discovery deduplication cache.
- `vault-log.md`: vault operation log.

Knowledge retrieval goes through QMD CLI, typically with `qmd query`, `qmd get`, and `qmd ls`; `_index.md` files are not required for lookup.
