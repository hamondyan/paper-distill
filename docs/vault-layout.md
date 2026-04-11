# Vault Layout

Paper Distill writes inside your Obsidian vault under `Paper Distill/`.

```text
Paper Distill/
├── inbox/
├── sources/
│   └── evidence/
├── wiki/
│   ├── papers/
│   ├── concepts/
│   ├── methods/
│   └── topics/
├── insights/
│   ├── queries/
│   ├── ideas/
│   ├── dialogues/
│   ├── digests/
│   └── memory-promotions/
├── memory/
├── zotero/
│   └── imports/
├── .state/
│   ├── ir/
│   └── memory/
├── index.md
└── log.md
```

## Visible User Layers

- `inbox/`: candidate papers awaiting approval.
- `sources/evidence/`: stable captured source evidence and sidecars.
- `wiki/papers/`: canonical per-paper work pages.
- `wiki/concepts/`: concept encyclopedia pages.
- `wiki/methods/`: method comparison pages.
- `wiki/topics/`: topic landscape pages.
- `insights/queries/`: saved query answers, comparisons, and reports.
- `insights/ideas/`: editable idea notes.
- `memory/`: current advisory memory views.
- `zotero/imports/`: local-first Zotero import packs.

## Hidden Machine State

- `.state/ir/`: extract and resolved IR JSON.
- `.state/memory/`: memory event state.
- `.state/paper-distill.db`: SQLite authority state.

## Navigation

- `index.md`: short human landing note.
- `log.md`: append-only knowledge-maintenance timeline.
- `_index.md`: minimal directory landing files only; they are not dashboards or backend source of truth.
