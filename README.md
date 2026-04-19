# Paper Distill

Paper Distill is a Markdown-first research knowledge system for chat-only discovery, direct paper capture, preserving raw evidence, and turning papers into canonical wiki pages.

v3.0 uses qmd as the read/index path, keeps Markdown as the source of truth, and gives business workflows to a small MCP surface.

## Why Paper Distill

Most research stacks are good at one layer and fuzzy everywhere else: they can search, or summarize, or store notes, but they do not keep a clean boundary between discovery, capture, retrieval, and canonical synthesis.

Paper Distill is built around those boundaries:

- discovery returns transient candidates in chat instead of pretending capture already happened
- capture is explicit and user-driven
- raw evidence is preserved before synthesis
- canonical pages are written through schema-validated tools
- retrieval and indexing go through QMD CLI instead of custom wrapper commands

The result is a vault that stays readable as plain Markdown while still being usable by agents.

## What It Does

- Discover candidate papers from configured topics or direct research queries as chat-only discovery results.
- Capture selected papers from resolved arXiv URLs, IDs, or DOI values.
- Ingest direct arXiv references into `raw/evidence/`.
- Distill captured papers into canonical `wiki/papers/` pages with required metadata and concept links.
- Maintain canonical concept pages, idea notes, and conversation insights through deterministic write tools.
- Audit vault health with schema-aware linting and a high-level `/status` snapshot.

## Core Workflow

The normal workflow is:

```text
/discover -> agent presents chat-only candidates -> /ingest <resolved arXiv URL|ID|DOI> -> raw evidence -> distill_paper -> qmd update -> /lint
```

Direct ingestion is available when you already know the paper identity:

```text
/ingest https://arxiv.org/abs/2410.24164
/ingest 10.48550/arxiv.2410.24164
/ingest 1706.03762
/ingest openvla, octo, diffusion policy
```

The agent resolves natural references to arXiv identities before capture. After write-heavy work, run `qmd update`; run `qmd embed -f` only when semantic retrieval must reflect new content immediately.

## Architecture At A Glance

Paper Distill has three clear surfaces:

1. Markdown vault: the durable knowledge layer under `raw/evidence/`, `wiki/`, and `insights/`
2. Business MCP: discovery, ingest, deterministic writes, concept maintenance, and linting
3. QMD CLI: query, get, status, collections, contexts, and index refresh

In practice that means:

- QMD CLI is the only read/index path.
- Paper Distill business MCP tools own discovery, direct ingest, deterministic writes, and linting.
- `qmd update` and `qmd embed -f` are explicit follow-up steps, not hidden side effects.
- Markdown files remain inspectable and editable as project artifacts, but canonical writes are routed through tools so validation stays enforced.

For the repo-level architecture guide, see [docs/architecture.md](docs/architecture.md). For QMD usage, see [docs/qmd-cli.md](docs/qmd-cli.md).

## Quickstart

1. Install dependencies:

```bash
uv sync
```

2. Configure `settings.json` with an absolute `paper_distill.vault_path`:

```bash
cp settings.example.json settings.json
```

3. Verify the local entrypoints:

```bash
uv run paper-distill-admin --help
qmd --help
```

4. Bootstrap the vault layout and QMD mappings:

```bash
uv run paper-distill-admin bootstrap
```

5. Start the MCP server:

```bash
uv run paper-distill-server
```

6. Run the first workflow:

```text
/discover
/ingest 10.48550/arxiv.2410.24164
qmd query "your topic"
```

When installed as a namespaced plugin, slash commands may appear with a plugin prefix such as `/paper-distill:discover`.

## Plugin Root

Paper Distill uses the repository root as the plugin root. Installation means registering this checkout with the host rather than moving the project into a separate plugin bundle.
Codex can also discover Paper Distill from the repo-local marketplace at `.agents/plugins/marketplace.json`.
That marketplace entry points at `./plugins/paper-distill`, a Codex compatibility plugin that resolves back to the repository root at runtime.

For host-specific installation and uninstall notes, see [docs/plugin-installation.md](docs/plugin-installation.md).

## Commands

| Command | Use it when | Backing surface |
| --- | --- | --- |
| `/discover` | you want new papers, a daily digest, or a topic search | `discover_papers` |
| `/ingest` | you want to capture resolved arXiv URLs, IDs, or DOI values | `ingest_and_read` |
| MCP `distill_paper(s)` | you want to turn captured evidence into canonical paper pages | `distill_paper`, `distill_papers` |
| `/lint` | you want a structural and weak-link audit of the vault | `lint_vault` |
| `/status` | you want a quick health snapshot and next action | agent-side summary |

For command details, see [docs/commands.md](docs/commands.md).

Installed agents also receive a short capability index at session start: use `discover_papers` for new papers, `qmd query` / `qmd get` for existing vault content, `distill_paper(s)` for captured evidence, `upsert_wiki_page` for canonical writes, and `lint_vault` for structural and decorative-link checks.

## Vault Layout

```text
vault/
├── raw/evidence/
├── wiki/papers/
├── wiki/concepts/
├── insights/ideas/
├── insights/conversations/
├── exports/presentations/
├── vault-log.md
└── .state/
```

This layout keeps candidate intake, preserved source material, canonical knowledge, and higher-level insights separate on purpose.

## Development

Run the main verification commands:

```bash
uv run python -m pytest -q
uv run python -m compileall -q server tests
```

Useful focused checks:

```bash
uv run python -m pytest tests/test_v3_commands.py tests/test_no_retired_names.py tests/test_skill_inventory.py tests/test_v3_conversations.py -q
qmd --help
qmd status
```

If `qmd query` does not show recent writes, run `qmd update`; run `qmd embed -f` when semantic retrieval needs to be current immediately.

## Documentation

- [Installation](docs/installation.md)
- [Plugin Installation](docs/plugin-installation.md)
- [Commands](docs/commands.md)
- [Architecture](docs/architecture.md)
- [QMD CLI Guide](docs/qmd-cli.md)
- [Frontmatter Reference](docs/frontmatter-reference.md)
- [Vault Layout](docs/vault-layout.md)
- [Testing](docs/testing.md)

## Project Status

Paper Distill is in an active v3 phase: the FastMCP backend, QMD CLI boundary, progressive-disclosure skills, schema-validated writes, and vault health flows are in place, while the surrounding product surface is still being tightened.
