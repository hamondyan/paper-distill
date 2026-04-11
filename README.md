# Paper Distill

Paper Distill is an Obsidian-first research knowledge system for paper discovery, evidence capture, wiki compilation, query synthesis, and idea generation.

It is built around one rule: papers only become long-term knowledge after a human approves them.

## What It Does

- Discovers candidate papers from arXiv, Semantic Scholar, OpenAlex, DBLP, and Papers with Code.
- Stages candidates in `Paper Distill/inbox/` for human approval.
- Captures approved papers into `Paper Distill/sources/evidence/`.
- Maintains canonical paper pages in `Paper Distill/wiki/papers/`.
- Compiles reusable wiki pages for concepts, methods, topics, and paper syntheses.
- Saves substantive research answers into `Paper Distill/insights/queries/`.
- Writes research ideas as editable notes in `Paper Distill/insights/ideas/`.
- Supports Zotero handoff through `local_first`, `web_api`, or `disabled` modes.
- Exposes everything through MCP tools for Codex, Claude, and OpenClaw-style agents.

## Core Flow

```text
discover -> inbox approval -> sources/evidence -> wiki/papers -> query / ideas / compile
```

Directly approved papers can skip discovery:

```text
add-paper -> sources/evidence -> wiki/papers
```

## Common Usage

- Find papers: `/discover vision language action manipulation`
- Add a known paper: `/add-paper 10.48550/arxiv.2410.24164`
- Process approved inbox items: `/process-inbox`
- Ask the vault a research question: `/query what VLA architectures are in my library?`
- Refresh compiled knowledge: `/compile`
- Generate research ideas: `/ideas`
- Check vault health: `/lint`
- Preview one paper without ingestion: `/summarize <doi|url>`

## Vault Shape

```text
Paper Distill/
├── inbox/
├── sources/evidence/
├── wiki/papers/
├── wiki/concepts/
├── wiki/methods/
├── wiki/topics/
├── insights/queries/
├── insights/ideas/
├── memory/
├── zotero/imports/
└── .state/
```

## Documentation

- [Installation](docs/installation.md)
- [Configuration](docs/configuration.md)
- [Commands](docs/commands.md)
- [Workflows](docs/workflows.md)
- [Vault Layout](docs/vault-layout.md)
- [Architecture](docs/architecture.md)
- [Testing](docs/testing.md)
- [Obsidian CLI Validation](docs/obsidian-cli-validation.md)
- [TODO Status](docs/todo.md)

## License

MIT
