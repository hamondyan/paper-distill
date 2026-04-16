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
        "keywords": ["manipulation", "robot learning"],
        "weight": 1.0
      }
    }
  }
}
```

`VAULT_PATH` overrides `paper_distill.vault_path`.

## Top-Level Settings

| Key | Type | Description |
|-----|------|-------------|
| `vault_path` | string | Absolute path to the vault root. |
| `topics` | object | Named research directions used by discovery and scoring. |
| `search` | object | Source selection and result caps. |
| `workflow` | object | Inbox card and discovery selection behavior. |
| `capture` | object | arXiv capture cleaning and fidelity controls. |
| `venue` | object | Venue authority order. |
| `scoring` | object | Discovery ranking weights and venue tiers. |
| `research_profile` | object | Free-text direction, seed papers, preferred authors, and feedback counters. |

## Search

| Key | Default | Description |
|-----|---------|-------------|
| `search.sources` | `["arxiv", "s2", "openalex", "dblp", "pwc"]` | Paper sources used by discovery. |
| `search.max_per_topic` | `20` | Maximum results per topic. |
| `search.max_daily` | `10` | Maximum candidates retained per discovery run. |

## Workflow

| Key | Default | Description |
|-----|---------|-------------|
| `workflow.detailed_inbox_cards` | `true` | Write detailed inbox stubs. |
| `workflow.max_candidates_per_topic` | `5` | Limit candidates retained for each topic. |
| `workflow.diversity_cap_per_cluster` | `2` | Limit near-duplicate title clusters. |
| `workflow.require_arxiv_binding` | `true` | Prefer candidates with arXiv capture support. |

## Capture

| Key | Default | Description |
|-----|---------|-------------|
| `capture.cleaning_scope` | `"body_abstract_sections_captions"` | HTML cleaning scope. |
| `capture.appendix_policy` | `"summary_only"` | Appendix handling policy. |
| `capture.failure_policy` | `"return_to_inbox"` | How capture failure is reported to the user. |
| `capture.min_body_chars` | `1500` | Minimum accepted captured body length. |
| `capture.preserve_math` | `true` | Preserve math blocks. |
| `capture.preserve_figures` | `true` | Preserve figure captions. |
| `capture.preserve_tables` | `true` | Preserve table content. |
| `capture.remove_refs` | `true` | Remove bibliography text. |
| `capture.remove_inline_citations` | `false` | Remove inline numeric citations. |
| `capture.remove_internal_links` | `true` | Remove internal paper cross-references. |
| `capture.write_structured_sidecar` | `true` | Write structured capture sidecars when available. |
| `capture.extract_figure_assets` | `false` | Extract figure assets. |
| `capture.max_figures` | `12` | Maximum figures to extract. |
| `capture.max_tables` | `12` | Maximum tables to extract. |
| `capture.max_equations` | `24` | Maximum equations to extract. |

## Scoring

Default weights:

| Key | Default |
|-----|---------|
| `topic_fit` | `0.40` |
| `recency` | `0.20` |
| `novelty` | `0.15` |
| `impact` | `0.10` |
| `venue_tier` | `0.07` |
| `author_preference` | `0.05` |
| `metadata_quality` | `0.03` |

Venue aliases and venue tiers normalize discovery results before scoring.

## Research Profile

| Key | Description |
|-----|-------------|
| `research_profile.direction` | Free-text research direction shown to the agent. |
| `research_profile.whitelist_authors` | Author names that boost discovery scoring. |
| `research_profile.seed_papers` | Seed DOI or arXiv IDs for local relevance. |
| `research_profile.learned_preferences.accepted_keywords` | Accepted keyword feedback. |
| `research_profile.learned_preferences.rejected_keywords` | Rejected keyword feedback. |
| `research_profile.learned_preferences.preferred_venues` | Preferred venue feedback. |
| `research_profile.learned_preferences.feedback_count` | Number of feedback cycles represented in settings. |

## Environment Variables

| Variable | Description |
|----------|-------------|
| `VAULT_PATH` | Overrides `paper_distill.vault_path`. |
| `SETTINGS_PATH` | Points to a custom settings JSON file. |
| `PAPER_DISTILL_QMD_BINARY` | Overrides the qmd executable name. |
