# Configuration

Configuration lives in `settings.json` by default. Point to another file with `SETTINGS_PATH`.

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

## Complete Default Values

All settings below reflect `_DEFAULT_PAPER_DISTILL_SETTINGS` in `server/config.py`. Any key you omit falls back to these defaults.

### vault_path

| Key | Type | Default | Description |
|-----|------|---------|-------------|
| `vault_path` | string | `""` | Absolute path to the Obsidian vault root. Overridden by `VAULT_PATH` env var. |

### topics

Named research directions for discovery and scoring.

```json
"topics": {
  "my-topic": {
    "label": "Human-readable label",
    "keywords": ["keyword1", "keyword2"],
    "aliases": [],
    "must_include": [],
    "must_exclude": []
  }
}
```

`must_include` tokens are prefixed `+` in search queries; `must_exclude` are prefixed `-`.

### search

| Key | Type | Default | Description |
|-----|------|---------|-------------|
| `search.sources` | list | `["arxiv", "semantic_scholar", "openalex", "dblp", "papers_with_code"]` | Active paper sources |
| `search.max_per_topic` | int | `20` | Maximum results per topic per search run |
| `search.max_daily` | int | `10` | Maximum results to keep per topic in daily digest |

### workflow

| Key | Type | Default | Description |
|-----|------|---------|-------------|
| `workflow.detailed_inbox_cards` | bool | `true` | Write full metadata to inbox cards |
| `workflow.max_candidates_per_topic` | int | `5` | Cap on scored candidates shown per topic |
| `workflow.diversity_cap_per_cluster` | int | `2` | Max papers per title-cluster in results |
| `workflow.require_arxiv_binding` | bool | `true` | Reject candidates without an arXiv ID |

### capture

| Key | Type | Default | Description |
|-----|------|---------|-------------|
| `capture.cleaning_scope` | string | `"full"` | How much of the HTML to clean (`"full"` or `"abstract_only"`) |
| `capture.appendix_policy` | string | `"summary_only"` | `"full"`, `"summary_only"`, or `"none"` |
| `capture.failure_policy` | string | `"return_to_inbox"` | On capture failure: `"return_to_inbox"` or `"skip"` |
| `capture.min_body_chars` | int | `1500` | Minimum body text length before capture is accepted |
| `capture.preserve_math` | bool | `true` | Keep LaTeX math blocks in captured content |
| `capture.preserve_figures` | bool | `true` | Keep figure captions |
| `capture.preserve_tables` | bool | `true` | Keep table content |
| `capture.remove_refs` | bool | `true` | Strip bibliography section |
| `capture.remove_inline_citations` | bool | `false` | Strip inline `[1]` citation markers |
| `capture.remove_internal_links` | bool | `true` | Strip `§2.1` section cross-references |
| `capture.write_structured_sidecar` | bool | `true` | Write `.sidecar.json` with structured sections |
| `capture.extract_figure_assets` | bool | `false` | Extract figure images into source assets |
| `capture.max_figures` | int | `12` | Maximum figures to extract per paper |
| `capture.max_tables` | int | `12` | Maximum tables to extract per paper |
| `capture.max_equations` | int | `24` | Maximum equations to extract per paper |

### venue

| Key | Type | Default | Description |
|-----|------|---------|-------------|
| `venue.authority_order` | list | `["dblp", "crossref", "openalex", "arxiv"]` | Priority order for venue name normalization |

### scoring.weights

Nine factors, all configurable. Default weights sum to 1.00.

| Key | Default | What it measures |
|-----|---------|-----------------|
| `scoring.weights.topic_fit` | `0.40` | Keyword overlap with configured topics |
| `scoring.weights.recency` | `0.20` | Publication date (exponential decay) |
| `scoring.weights.novelty` | `0.15` | Inverse of existing library coverage |
| `scoring.weights.impact` | `0.10` | Citation count (log-scaled) |
| `scoring.weights.venue_tier` | `0.07` | Tier-S / Tier-A venue membership |
| `scoring.weights.author_preference` | `0.05` | Whitelist author match |
| `scoring.weights.metadata_quality` | `0.03` | Completeness of title/abstract/DOI |

### scoring.venue_tiers

```json
"scoring": {
  "venue_tiers": {
    "tier_s": ["NeurIPS", "ICML", "ICLR", "CoRL", "RSS", "CVPR", "ECCV", "ICCV"],
    "tier_a": ["IROS", "ICRA", "RA-L", "TMLR", "JMLR", "ACL", "EMNLP"]
  },
  "venue_aliases": {
    "neural information processing systems": "NeurIPS",
    "international conference on machine learning": "ICML"
  }
}
```

### concept_registry

| Key | Type | Default | Description |
|-----|------|---------|-------------|
| `concept_registry.abbreviation_whitelist` | dict | See below | Maps abbreviations to canonical expanded forms for auto-merge |

Default abbreviation whitelist:

```json
{
  "vla": "vision-language-action",
  "vlm": "vision-language-model",
  "llm": "large-language-model",
  "rl": "reinforcement-learning",
  "il": "imitation-learning",
  "bc": "behavior-cloning",
  "vit": "vision-transformer",
  "cnn": "convolutional-neural-network",
  "gan": "generative-adversarial-network",
  "nerf": "neural-radiance-field",
  "slam": "simultaneous-localization-and-mapping",
  "mpc": "model-predictive-control",
  "ppo": "proximal-policy-optimization",
  "dpo": "direct-preference-optimization",
  "sac": "soft-actor-critic",
  "ddpm": "denoising-diffusion-probabilistic-model",
  "dit": "diffusion-transformer",
  "moe": "mixture-of-experts",
  "lora": "low-rank-adaptation",
  "rag": "retrieval-augmented-generation",
  "rt": "robotics-transformer"
}
```

Values are slug-normalized before comparison, so `"Diffusion Policy"` and `"diffusion-policy"` are equivalent. Add project-specific abbreviations here instead of changing code.

### zotero

| Key | Type | Default | Description |
|-----|------|---------|-------------|
| `zotero.enabled` | bool | `true` | Enable or disable Zotero handoff entirely |
| `zotero.mode` | string | `"local_first"` | `"local_first"`, `"web_api"`, or `"disabled"` |
| `zotero.auto_collect` | bool | `false` | Automatically collect papers during ingest |
| `zotero.collection_name` | string | `"Paper Distill"` | Zotero collection to write to |
| `zotero.local_export_dir` | string | `"zotero/imports"` | Vault-relative path for local import packs |
| `zotero.local_export_format` | string | `"csljson"` | Export format for local packs |

**Zotero modes:**
- `local_first`: writes local import packs under `Paper Distill/zotero/imports/`. Drag-and-drop into Zotero.
- `web_api`: writes directly through the Zotero Web API. Requires `ZOTERO_LIBRARY_ID` and `ZOTERO_API_KEY`.
- `disabled`: skips Zotero handoff entirely.

### research_profile

| Key | Type | Default | Description |
|-----|------|---------|-------------|
| `research_profile.direction` | string | `""` | Free-text research direction shown to the agent |
| `research_profile.whitelist_authors` | list | `[]` | Author names that boost scoring |
| `research_profile.seed_papers` | list | `[]` | DOIs/arXiv IDs of seed papers for novelty baseline |
| `research_profile.learned_preferences.accepted_keywords` | list | `[]` | Auto-updated by `update_learned_preferences` |
| `research_profile.learned_preferences.rejected_keywords` | list | `[]` | Auto-updated by `update_learned_preferences` |
| `research_profile.learned_preferences.preferred_venues` | list | `[]` | Auto-updated by `update_learned_preferences` |
| `research_profile.learned_preferences.feedback_count` | int | `0` | Number of feedback cycles applied |

`learned_preferences` is updated atomically by the `update_learned_preferences` MCP tool. Do not edit manually while the server is running.

## Obsidian Query Providers

`query-library` prefers Obsidian CLI-backed structured querying when configured:

1. Official Obsidian CLI through the built-in normalization adapter.
2. Filesystem frontmatter scan fallback.

If no Obsidian provider is available, or if `vault_path` is not the vault currently open in Obsidian, Paper Distill still works through the fallback provider and reports `provider: filesystem_scan`.

See [Obsidian CLI Validation](obsidian-cli-validation.md) for the current capability matrix.

### obsidian_query

| Key | Type | Default | Description |
|-----|------|---------|-------------|
| `obsidian_query.command` | string | `""` | Custom CLI command override (advanced; must return normalized `query-library` JSON) |

## Environment Variables

| Variable | Description |
|----------|-------------|
| `VAULT_PATH` | Overrides `paper_distill.vault_path` |
| `SETTINGS_PATH` | Points to a custom settings JSON file |
| `ZOTERO_LIBRARY_ID` | Required for Zotero `web_api` mode |
| `ZOTERO_API_KEY` | Required for Zotero `web_api` mode |
