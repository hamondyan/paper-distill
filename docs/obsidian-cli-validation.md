# Obsidian CLI Validation

Date: 2026-04-11

This page records the real-environment validation of the Obsidian CLI and Bases
commands used as the only Obsidian-backed query integration for Paper Distill.

## Environment

- Vault: `/Users/huang/Documents/knowledge_repo`
- Paper Distill workspace in vault: `Paper Distill/`
- Obsidian binary: `/Applications/Obsidian.app/Contents/MacOS/obsidian`
- Obsidian version: `1.12.4`
- Obsidian CLI setting: enabled
- Vault state in Obsidian config: open
- Bases core plugin: enabled
- `paper_distill.obsidian_query`: empty in the active `settings.json`

## Capability Matrix

| Capability | Result | Evidence | Notes |
| --- | --- | --- | --- |
| Visible file listing | Pass | `obsidian files folder="Paper Distill/obsidian-validation"` returned the temporary note and `.base` file. | Good fit for visible vault assets. |
| Keyword search | Pass | `obsidian search ... format=json` returned `["Paper Distill/obsidian-validation/cli-validation-note.md"]`. | Works for visible Markdown content. |
| Property read | Pass | `obsidian properties ... format=json` returned `type`, `status`, `topic`, and `tags`; `property:read name=status` returned `approved`. | Structured properties are available. |
| Tag read | Partial | `obsidian tags ... format=json` returned JSON, but `obsidian tag name=... verbose format=json` returned TSV-like text. | Use path-scoped `tags` JSON or normalize the verbose output explicitly. |
| Bases query | Pass | `obsidian base:query ... view=Validation format=json` returned a JSON row for the temporary note. | Output column names can be localized, for example `名称`; adapters must normalize keys. |
| Hidden `.state` indexing | Fail by design | Hidden validation files under `Paper Distill/.state/obsidian-validation` were not listed or searched; `base:query` reported the hidden base file as not found. | Do not depend on Obsidian CLI/Bases for hidden IR or other `.state` assets. |
| Paper Distill provider selection | Pass | `available_obsidian_query_providers()` reported `official_cli`; `query_library_sync(...)` returned `provider=official_cli` and `fallback_used=False` for the open vault. | The adapter falls back to filesystem scan when `vault_path` is not the vault currently open in Obsidian. |

## Decisions

- Obsidian CLI is the only Obsidian-backed provider family retained.
- Native CLI/Bases commands are viable primitives for visible vault queries:
  list, keyword search, properties, tags, and base queries all work.
- Native CLI output is normalized inside `server/obsidian_query.py` for
  `query-library` list, property filter, tag/topic filter, compact/full detail,
  sort, limit, and days-back behavior.
- Hidden JSON IR should stay under `.state/` and should not be part of the
  Obsidian query provider contract.
- The supported runtime behavior is Obsidian CLI first for the open vault, with
  `filesystem_scan` as the reliable offline and temporary-vault fallback.
