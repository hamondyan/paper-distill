# Paper Distill

Paper Distill is a human-approved research workflow for Obsidian:

- discover papers from multiple sources
- keep only arXiv-backed candidates
- capture cleaned `raw/source` notes from ar5iv
- generate `raw/notes` with the `CRGP-DNL` reading template
- compile evidence-backed wiki pages
- hand approved papers off to Zotero in `local_first` or `web_api` mode

The current default is `local_first` Zotero mode, which writes local import packs instead of creating cloud items.

## Core Flow

```text
discover -> inbox approval -> raw/source -> raw/notes -> Zotero handoff -> wiki
```

## Client Support

This repository is laid out to work as a bundle for:

- Claude
- Codex
- OpenClaw

All three clients share the same MCP server entrypoint through [./.mcp.json](/Users/huang/Desktop/paper-distill-v2/.mcp.json). Client-specific details are summarized in [docs/CLIENTS.md](/Users/huang/Desktop/paper-distill-v2/docs/CLIENTS.md).

## Zotero Modes

- `local_first`: export local CSL-JSON import packs under `Paper Distill/zotero/imports/`
- `web_api`: create items in the configured Zotero Web API library
- `disabled`: skip Zotero handoff entirely

Configure these in [settings.json](/Users/huang/Desktop/paper-distill-v2/settings.json) or through environment variables.
