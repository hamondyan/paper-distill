# Configuration

Configuration lives in `settings.json` by default. You can also point to another file with `SETTINGS_PATH`.

## Minimal Configuration

```json
{
  "paper_distill": {
    "vault_path": "/absolute/path/to/your/obsidian/vault",
    "topics": {
      "manipulation": {
        "label": "Robot Manipulation",
        "keywords": ["manipulation", "robot learning"]
      }
    },
    "zotero": {
      "enabled": true,
      "mode": "local_first"
    }
  }
}
```

## Important Sections

- `vault_path`: absolute path to the Obsidian vault.
- `topics`: named research directions used for discovery and scoring.
- `search`: source list and per-topic result limits.
- `workflow`: inbox-card detail, diversity caps, and arXiv binding requirements.
- `capture`: arXiv/PDF capture policy, sidecar generation, and figure/table/equation limits.
- `scoring`: topic-fit, recency, novelty, venue, author, and metadata weights.
- `concept_registry`: concept registry behavior, including abbreviation auto-merge whitelist.
- `obsidian_query`: optional Obsidian CLI query integration.
- `zotero`: Zotero handoff mode and local export settings.
- `research_profile`: direction, seed papers, authors, and learned preferences.

## Zotero Modes

- `local_first`: writes local import packs under `Paper Distill/zotero/imports/`.
- `web_api`: writes directly through the Zotero Web API.
- `disabled`: skips Zotero handoff.

For the most predictable local workflow, use `local_first` or `disabled`.

## Concept Registry

`paper_distill.concept_registry.abbreviation_whitelist` controls abbreviation
auto-merges, for example mapping `vla` to `vision-language-action`. Values are
slug-normalized before comparison, so `"Diffusion Policy"` and
`"diffusion-policy"` are equivalent as expanded forms. Add project-specific
abbreviations here instead of changing code.

## Obsidian Query Providers

`query-library` prefers Obsidian CLI-backed structured querying when configured:

1. Official Obsidian CLI through the built-in normalization adapter.
2. Filesystem frontmatter scan fallback.

If no Obsidian provider is available, or if `vault_path` is not the vault currently open in Obsidian, Paper Distill still works through the fallback provider and reports `provider: filesystem_scan`.

The native adapter calls Obsidian `files` and `properties`, then normalizes the
result to the same `query-library` contract as filesystem scan. A custom
`paper_distill.obsidian_query.command` may still be supplied for specialized
setups; if present, it must return normalized `query-library` JSON. See
[Obsidian CLI Validation](obsidian-cli-validation.md) for the current capability
matrix.

## Environment Variables

- `VAULT_PATH`: overrides `paper_distill.vault_path`.
- `SETTINGS_PATH`: points to a custom settings JSON file.
- Zotero-specific credentials can also be provided through environment variables when using Web API mode.
