# Compile IR Schema

The Extract → Resolve → Write (EDC) pipeline uses JSON IR files stored in `.state/ir/`. This document describes the schema for both raw IR (`{citekey}.json`) and resolved IR (`{citekey}_resolved.json`).

Schema version: `2024-06` (from `server/compile_ir.py`).

---

## File Locations

| File | Written by | Description |
|------|-----------|-------------|
| `.state/ir/{citekey}.json` | `paper-distill-extract` | Raw IR from Extract stage |
| `.state/ir/{citekey}_resolved.json` | `knowledge-compile-resolve` | Resolved IR with concept registry links |

---

## Raw IR Schema

### Required top-level fields

These fields must be present or `paper-distill-extract` will return a validation error.

| Field | Type | Description |
|-------|------|-------------|
| `citekey` | string | Must match the source evidence filename |
| `title` | string | Paper title |
| `authors` | list[string] | Author names |
| `tension_fields` | dict | Required sub-schema (see below) |
| `candidate_concepts` | list[dict] | Concepts extracted from the paper |

### tension_fields sub-schema

All four keys are required.

| Field | Type | Description |
|-------|------|-------------|
| `limitations` | list[string] | What the paper explicitly acknowledges it cannot do or handles poorly |
| `assumptions` | list[string] | Stated or implicit assumptions in the methodology |
| `open_questions` | list[string] | Questions the paper raises but does not answer |
| `negative_results` | list[string] | Experiments or claims that failed or were disproved |

Two optional tension fields:

| Field | Type | Description |
|-------|------|-------------|
| `failure_modes` | list[string] | Known failure conditions in deployment |
| `transfer_constraints` | list[string] | Limitations on generalization to new domains |

### candidate_concepts items

Each item in `candidate_concepts` represents a concept surface form found in the paper.

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `surface_form` | string | yes | Concept as it appears in the paper text |
| `concept_type` | string | no | `"concept"`, `"method"`, or `"topic"` |
| `context` | string | no | Sentence or phrase where the concept appears |
| `importance` | string | no | `"primary"`, `"secondary"`, or `"background"` |

### Optional top-level fields

| Field | Type | Description |
|-------|------|-------------|
| `schema_version` | string | IR schema version (e.g., `"2024-06"`) |
| `abstract` | string | Paper abstract |
| `year` | int | Publication year |
| `venue` | string | Normalized venue name |
| `doi` | string | DOI |
| `arxiv_id` | string | arXiv ID |
| `sections` | list[dict] | Structured section list with `heading`, `level`, `summary` |
| `methods` | list[string] | Named methods used in the paper |
| `datasets` | list[string] | Datasets used |
| `metrics` | list[string] | Evaluation metrics |
| `contributions` | list[string] | Author-stated contributions |
| `related_work` | list[string] | Citekeys of closely related papers |

---

## Resolved IR Schema

`{citekey}_resolved.json` is produced by `knowledge-compile-resolve`. It extends the raw IR with concept registry links.

### Additional fields in resolved IR

| Field | Type | Description |
|-------|------|-------------|
| `resolved_concepts` | list[dict] | Concept registry entries linked to `candidate_concepts` |
| `resolve_timestamp` | string | ISO 8601 timestamp of resolution |
| `schema_version` | string | `"2024-06"` |

### resolved_concepts items

Each item corresponds to a `candidate_concepts` entry, enriched with registry data.

| Field | Type | Description |
|-------|------|-------------|
| `surface_form` | string | Original surface form from the paper |
| `canonical` | string | Canonical concept name from registry |
| `slug` | string | URL-safe registry slug |
| `concept_id` | string | Stable registry ID |
| `concept_type` | string | `"concept"`, `"method"`, or `"topic"` |
| `registered` | bool | Whether this was newly registered during resolve |
| `merged_into` | string \| null | Canonical slug if auto-merged |

---

## Example Raw IR

```json
{
  "schema_version": "2024-06",
  "citekey": "chi2023diffusionpolicy",
  "title": "Diffusion Policy: Visuomotor Policy Learning via Action Diffusion",
  "authors": ["Cheng Chi", "Siyuan Feng", "Yilun Du"],
  "year": 2023,
  "venue": "RSS",
  "arxiv_id": "2303.04137",
  "tension_fields": {
    "limitations": [
      "Inference speed is slower than regression-based policies due to iterative denoising",
      "Requires significant compute for training on high-resolution images"
    ],
    "assumptions": [
      "Demonstrations are provided by a kinesthetically-taught robot arm",
      "Action space is assumed to be low-dimensional and continuous"
    ],
    "open_questions": [
      "How does the approach scale to multi-modal, language-conditioned tasks?",
      "Can denoising steps be reduced without quality loss?"
    ],
    "negative_results": [
      "Simple regression baselines outperform diffusion on unimodal tasks"
    ]
  },
  "candidate_concepts": [
    {
      "surface_form": "Diffusion Policy",
      "concept_type": "method",
      "importance": "primary"
    },
    {
      "surface_form": "DDPM",
      "concept_type": "concept",
      "importance": "secondary"
    },
    {
      "surface_form": "behavior cloning",
      "concept_type": "method",
      "importance": "background"
    }
  ],
  "contributions": [
    "First application of diffusion models to robot visuomotor policy learning",
    "Demonstrates multimodal action distribution capture"
  ]
}
```

---

## Validation

`paper-distill-extract` validates the IR before writing. On error, it returns:

```json
{
  "valid": false,
  "errors": [
    "Missing required field: tension_fields.open_questions",
    "candidate_concepts[0] missing required field: surface_form"
  ]
}
```

Fix all errors before proceeding to the Resolve stage.
