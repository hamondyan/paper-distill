# Configuration

Configuration lives only in the repository-root `settings.json`. `server/config.py` is a strict reader and validator; it does not provide business defaults or environment-variable overrides.

## Full Configuration Shape

```json
{
  "paper_distill": {
    "vault_path": "/absolute/path/to/your/obsidian/vault",
    "qmd": {
      "binary": "qmd"
    },
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

## Top-Level Settings

| Key | Type | Description |
|-----|------|-------------|
| `vault_path` | string | Absolute path to the vault root. |
| `qmd` | object | QMD executable settings. |
| `topics` | object | Named research directions used by discovery and scoring. |
| `search` | object | Source selection and result caps. |
| `workflow` | object | Discovery candidate limits and capture eligibility preferences. |
| `capture` | object | arXiv capture cleaning and fidelity controls. |
| `venue` | object | Venue authority order. |
| `scoring` | object | Discovery ranking weights and venue tiers. |
| `research_profile` | object | Free-text direction, seed papers, preferred authors, and feedback counters. |

## QMD

| Key | Type | Description |
|-----|------|-------------|
| `qmd.binary` | string | Executable name or absolute path used for QMD CLI calls. |

## Search

| Key | Type | Description |
|-----|------|-------------|
| `search.sources` | array of strings | Paper sources used by discovery. |
| `search.max_per_topic` | integer | Maximum results per topic. |
| `search.max_daily` | integer | Maximum candidates retained per discovery run. |
| `search.contact_email` | string | Contact email used for OpenAlex and Crossref requests. Use an empty string if you do not want to send one. |
| `search.unpaywall_email` | string | Contact email used for Unpaywall requests. Use an empty string to disable Unpaywall lookups. |
| `search.semantic_scholar_api_key` | string | Optional Semantic Scholar API key. Use an empty string for anonymous requests. |

## Workflow

| Key | Type | Description |
|-----|------|-------------|
| `workflow.max_candidates_per_topic` | integer | Limit candidates retained for each topic. |
| `workflow.diversity_cap_per_cluster` | integer | Limit near-duplicate title clusters. |
| `workflow.require_arxiv_binding` | boolean | Prefer candidates with arXiv capture support. |

## Capture

| Key | Type | Description |
|-----|------|-------------|
| `capture.cleaning_scope` | string | HTML cleaning scope. |
| `capture.appendix_policy` | string | Appendix handling policy. |
| `capture.failure_policy` | string | How capture failure is reported to the user. |
| `capture.min_body_chars` | integer | Minimum accepted captured body length. |
| `capture.preserve_math` | boolean | Preserve math blocks. |
| `capture.preserve_figures` | boolean | Preserve figure captions. |
| `capture.preserve_tables` | boolean | Preserve table content. |
| `capture.remove_refs` | boolean | Remove bibliography text. |
| `capture.remove_inline_citations` | boolean | Remove inline numeric citations. |
| `capture.remove_internal_links` | boolean | Remove internal paper cross-references. |
| `capture.write_structured_sidecar` | boolean | Write structured capture sidecars when available. |
| `capture.extract_figure_assets` | boolean | Extract figure assets. |
| `capture.max_figures` | integer | Maximum figures to extract. |
| `capture.max_tables` | integer | Maximum tables to extract. |
| `capture.max_equations` | integer | Maximum equations to extract. |

## Scoring

Required weights:

| Key | Type |
|-----|------|
| `topic_fit` | number |
| `recency` | number |
| `novelty` | number |
| `impact` | number |
| `venue_tier` | number |
| `author_preference` | number |
| `metadata_quality` | number |
| `profile_alignment` | number |
| `taste_alignment` | number |

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

## Validation Behavior

- `settings.json` must exist at the repository root.
- Invalid JSON raises a `ConfigError` that points to the file location.
- Missing required fields raise a `ConfigError` with the exact field path, for example `paper_distill.capture.max_figures`.
- Wrong field types raise a `ConfigError` with the exact field path.
- There are no environment-variable overrides; update `settings.json` directly.
