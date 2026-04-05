# Paper Distill

Paper Distill is a human-approved research workflow for Obsidian. It helps you:

- discover papers from multiple academic sources
- stage candidates in `inbox/` for review
- directly add user-confirmed papers into the vault with `add_paper`
- capture cleaned `raw/source` notes from ar5iv or recovered PDF text
- generate `raw/notes` with the `CRGP-DNL` reading template
- compile evidence-backed wiki pages
- optionally hand approved papers off to Zotero

The repository is packaged as one MCP-backed bundle for Claude, Codex, and OpenClaw.

## Core Flow

Normal discovery flow:

```text
discover -> inbox approval -> raw/source -> raw/notes -> Zotero handoff -> wiki
```

Direct-add flow for papers you already approved yourself:

```text
add-paper -> raw/source -> raw/notes -> Zotero handoff -> wiki
```

## Vault Layout

Paper Distill writes into your Obsidian vault under:

```text
{vault}/Paper Distill/
├── inbox/
├── raw/
│   ├── source/
│   └── notes/
├── zotero/
│   └── imports/
├── wiki/
│   ├── papers/
│   ├── concepts/
│   ├── methods/
│   └── topics/
├── daily-log/
└── queries/
```

## Quick Start

### 1. Point Paper Distill at Your Obsidian Vault

Set your vault path in [settings.json](/Users/huang/Desktop/paper-distill-v2/settings.json) under `paper_distill.vault_path`, or provide `VAULT_PATH` as an environment variable.

Example:

```json
{
  "paper_distill": {
    "vault_path": "/absolute/path/to/your/obsidian/vault"
  }
}
```

`VAULT_PATH` overrides `settings.json` when both are present.

### 2. Configure Your Research Profile

Paper ranking, recommendations, and downstream compilation are guided by `paper_distill.research_profile` in [settings.json](/Users/huang/Desktop/paper-distill-v2/settings.json).

The most important fields are:

- `direction`: your current research direction in one sentence
- `whitelist_authors`: authors you want the discovery pipeline to prioritize
- `seed_papers`: representative DOI list for topic calibration
- `learned_preferences`: feedback memory that can evolve over time

Example:

```json
{
  "paper_distill": {
    "research_profile": {
      "direction": "Embodied AI with vision-language-action policies for robot manipulation",
      "whitelist_authors": ["Sergey Levine", "Chelsea Finn"],
      "seed_papers": ["10.48550/arxiv.2410.24164"],
      "learned_preferences": {
        "accepted_keywords": [],
        "rejected_keywords": [],
        "preferred_venues": [],
        "feedback_count": 0
      }
    }
  }
}
```

If you want to change “论文偏好”, this is the main place to do it.

### 3. Choose a Zotero Mode

Paper Distill supports three Zotero modes:

- `local_first`: write local CSL-JSON import packs under `Paper Distill/zotero/imports/`
- `web_api`: create items in your Zotero library through the Zotero Web API
- `disabled`: skip Zotero handoff entirely

Important behavior differences:

- `local_first` does not write PDFs into Zotero `storage/` and does not choose a Zotero collection for you
- `web_api` can create Zotero items and may attempt to import or link PDF attachments
- `disabled` keeps the Paper Distill knowledge-base workflow but performs no Zotero action

The current default in [settings.json](/Users/huang/Desktop/paper-distill-v2/settings.json) is `local_first`.

### 4. Set Zotero Credentials Only If You Need Them

You only need `ZOTERO_LIBRARY_ID` and `ZOTERO_API_KEY` for `web_api` mode.

Recommended environment variables:

- `VAULT_PATH`
- `OPENALEX_EMAIL`
- `S2_API_KEY`
- `ZOTERO_MODE`
- `ZOTERO_COLLECTION_NAME`
- `ZOTERO_LOCAL_EXPORT_DIR`
- `ZOTERO_LIBRARY_ID`
- `ZOTERO_API_KEY`

Notes:

- `OPENALEX_EMAIL` is recommended for polite API usage
- `S2_API_KEY` is optional but improves Semantic Scholar access
- `ZOTERO_LOCAL_EXPORT_DIR` is used only in `local_first`
- relative `ZOTERO_LOCAL_EXPORT_DIR` values are resolved relative to your vault

## Running the Server

### Recommended: `uv`

The bundle launcher in [scripts/run-mcp.sh](/Users/huang/Desktop/paper-distill-v2/scripts/run-mcp.sh) uses `uv`:

```bash
uv --directory <repo-root> run paper-distill-server
```

So if you want to use this repo as-is with the bundled MCP setup, `uv` is the easiest and most direct option.

Typical commands:

```bash
uv sync
uv run paper-distill-server
```

### Using `conda`

You can still use `conda`, but there is one operational difference: the shipped launcher still expects `uv`.

Typical `conda` setup:

```bash
conda create -n paper-distill python=3.11
conda activate paper-distill
pip install -e .
paper-distill-server
```

If you run the server manually inside a `conda` environment, this is fine.

If you want to use the bundled plugin launcher unchanged, install `uv` as well, or edit [scripts/run-mcp.sh](/Users/huang/Desktop/paper-distill-v2/scripts/run-mcp.sh) to launch `paper-distill-server` from your activated environment.

Short version:

- `uv`: recommended, matches the repo's bundled runtime
- `conda`: workable, but you either keep `uv` installed or customize the launcher

## Commands and Workflows

Frequently used commands:

- `/discover <query>`: search and stage candidate papers into `inbox/`
- `/add-paper <doi|arxiv|url>`: directly add a paper you already approved
- `/process-inbox`: process `status=approved` inbox notes into `raw/`
- `/compile`: compile approved raw notes into `wiki/`
- `/query <question>`: ask questions against your approved knowledge base
- `/ideas`: generate research ideas from the existing knowledge graph
- `/summarize <doi|url>`: quickly inspect a paper before deciding what to do

## Zotero Behavior Summary

If you are deciding how tightly to integrate Zotero, this is the practical summary:

- `local_first`: Paper Distill writes import packs into the vault, not into Zotero's storage directory
- `web_api`: Paper Distill talks to the Zotero library API and may import/link attachments there
- `disabled`: no Zotero writes at all

So if your goal is “不要保存 PDF 到 Zotero 目录”, use `local_first` or `disabled`.

## Client Support

All supported clients share the same MCP server entrypoint through [./.mcp.json](/Users/huang/Desktop/paper-distill-v2/.mcp.json). Client-specific notes are summarized in [docs/CLIENTS.md](/Users/huang/Desktop/paper-distill-v2/docs/CLIENTS.md).
