# ArXiv Capture Modernization Design

## Goal

Modernize Paper Distill's arXiv HTML capture pipeline by selectively integrating the strongest parts of `arxiv2md` without replacing the existing downstream ingestion contract.

The upgraded pipeline should:

- preserve the existing `CleanedArxivDocument` interface and all downstream consumers
- improve formula and table rendering quality in Markdown output
- improve HTML source compatibility by trying `arxiv.org/html` before `ar5iv`
- introduce configurable citation, reference, and appendix filtering semantics
- split the current monolithic capture implementation into smaller, focused modules

## Non-Goals

- replacing the current `CleanedArxivDocument` payload with `arxiv2md`'s `IngestionResult`
- removing PDF fallback from Paper Distill
- rewriting CRGP-DNL generation logic
- adding a separate service dependency on `arxiv2md.org`
- introducing a hard runtime dependency on the full `arxiv2md` package

## Current State

The current arXiv capture implementation lives primarily in [`server/arxiv_capture.py`](/Users/huang/Desktop/paper-distill-v2/server/arxiv_capture.py). That file currently owns:

- arXiv binding
- HTML fetching from `ar5iv`
- HTML pre-cleaning
- section reconstruction
- appendix summarization
- figure, table, and equation extraction
- Markdown assembly
- structured quality metadata
- deterministic CRGP-DNL note generation

The main risks in the current design are:

- one large file mixes unrelated responsibilities
- table rendering is intentionally simplified and leaves quality on the table
- formula rendering is optimized for extraction stability more than Markdown fidelity
- HTML fetching relies directly on `ar5iv` instead of trying native arXiv HTML first
- reference and appendix handling are implemented with scattered string checks rather than a reusable filtering layer

## Design Principles

1. Preserve the evidence contract first.
   The output of capture must remain compatible with `CleanedArxivDocument`, structured sidecars, raw source notes, and CRGP-DNL generation.

2. Reuse proven logic where possible.
   Adopt `arxiv2md` code for fetch fallback, section normalization, MathML-to-LaTeX conversion, and table serialization where it improves quality without breaking Paper Distill's semantics.

3. Separate parsing from policy.
   HTML parsing, Markdown serialization, and filtering decisions should live in separate modules so appendix/reference/citation policy can evolve without rewriting parsers.

4. Keep fallback behavior conservative.
   HTML capture should improve, but PDF fallback remains required for ingestion resilience.

5. Make migration incremental.
   Refactor boundaries first, then swap in upgraded behaviors behind stable adapters.

## Target Architecture

The refactor keeps `server/arxiv_capture.py` as the public orchestration module, but moves lower-level responsibilities into focused helpers.

### Module Boundaries

#### `server/arxiv_capture.py`

Responsibilities after refactor:

- public dataclasses and entrypoints
- orchestration of fetch -> parse -> filter -> assemble
- `bind_paper_to_arxiv`
- `capture_arxiv_source`
- `build_crgp_dnl`

Responsibilities removed from this file:

- raw HTML fetch strategy
- section title normalization utilities
- low-level Markdown serialization helpers
- HTML figure/table/equation conversion internals

#### `server/arxiv_html_fetch.py`

Responsibilities:

- fetch native `https://arxiv.org/html/<id>` first
- fall back to `https://ar5iv.labs.arxiv.org/html/<id>` when native HTML is unavailable
- return both HTML content and fetch provenance
- centralize retry and timeout behavior

The implementation should borrow the strategy from `arxiv2md/src/arxiv2md/fetch.py`, but remain local to this repository and compatible with Paper Distill logging and config.

#### `server/arxiv_section_filters.py`

Responsibilities:

- normalize section titles
- support include/exclude title filters
- centralize matching for `references`, `bibliography`, `appendix`, and future section classes

This module should closely follow `arxiv2md/src/arxiv2md/sections.py`, with local naming and type adaptations.

#### `server/arxiv_markdown.py`

Responsibilities:

- convert MathML to LaTeX for Markdown rendering
- serialize tables more faithfully
- serialize figure-wrapped tables
- expose configurable handling of inline citations and internal section links

This module should reuse or adapt the following `arxiv2md` logic:

- `convert_all_mathml_to_latex`
- `_serialize_table`
- `_serialize_figure`
- citation link handling semantics

Paper Distill-specific additions:

- serializer helpers that return both Markdown blocks and structured extraction-friendly metadata where needed

#### `server/arxiv_html_parser.py`

Responsibilities:

- extract title, abstract, authors, and section hierarchy from HTML
- provide cleaner author extraction than the current implementation

This module should adapt `arxiv2md/src/arxiv2md/html_parser.py` where it improves quality, especially author cleanup and section tree building.

#### `server/arxiv_capture_adapter.py`

Responsibilities:

- adapt parser and serializer outputs into `CleanedArxivDocument`
- preserve Paper Distill-specific fields:
  - `sections`
  - `appendix_snapshot`
  - `quality`
  - `figures`
  - `tables`
  - `equations`
  - `capture_fidelity`

This adapter is the compatibility wall that allows lower-level improvements without rewriting downstream code.

## Data Contract Preservation

The refactor must preserve the current `CleanedArxivDocument` shape:

- `title`
- `abstract`
- `markdown`
- `sections`
- `appendix_snapshot`
- `quality`
- `figures`
- `tables`
- `equations`
- `capture_fidelity`

Downstream consumers that must remain compatible include:

- raw source note generation
- structured sidecar generation
- raw note frontmatter
- `build_crgp_dnl`
- direct-add and process-inbox ingestion flows
- tests that assert figure/table/equation counts and evidence labels

## Fetch and Fallback Design

### New Fetch Order

1. Try `https://arxiv.org/html/<arxiv_id>`
2. If the native HTML endpoint is unavailable or returns the known "no HTML version" failure condition, try `https://ar5iv.labs.arxiv.org/html/<arxiv_id>`
3. If both HTML sources fail inside ingestion, preserve the existing PDF fallback path

### Rationale

- native arXiv HTML is the preferred canonical source when available
- `ar5iv` remains valuable for papers that do not expose native HTML
- Paper Distill still needs PDF fallback for ingestion reliability, which `arxiv2md` does not provide as a primary ingest path

### Provenance

The fetch layer should expose a fetch source label such as:

- `arxiv_native_html`
- `ar5iv_html`
- `pdf_text_recovered`

`capture_method` should remain backward-compatible where existing downstream logic expects `ar5iv_html_cleaned`, but the implementation should prepare for richer provenance in sidecars or logs.

## Formula Handling Design

### Current Weakness

The current pipeline extracts stable equation text for structured use, but the Markdown body does not benefit from a full MathML-to-LaTeX rendering pass.

### New Behavior

- run a MathML-to-LaTeX normalization pass before Markdown serialization
- preserve current equation extraction logic for structured snapshots
- continue to use extraction-oriented fallbacks when MathML annotations are incomplete

### Compatibility Rule

There are now two different math outputs with different jobs:

- Markdown math for human/LLM readability
- structured equation snapshots for evidence capture

The implementation must not trade away structured equation extraction just to improve rendered Markdown.

## Table Handling Design

### Current Weakness

Current table extraction is intentionally lightweight. It produces adequate structured snapshots, but it does not handle many HTML table shapes as completely as `arxiv2md`.

### New Behavior

- adopt `arxiv2md`-style table serialization for:
  - plain `table`
  - `thead` / `tbody` / `tfoot`
  - figure-wrapped `ltx_table`
  - multiline cell normalization
- preserve current structured fields:
  - `label`
  - `caption`
  - `section`
  - `summary`
  - `markdown`
  - `row_count`
  - `column_count`

### Compatibility Rule

The structured snapshot remains the source of truth for downstream notes. Better table Markdown should improve `markdown` payload quality, not replace structured extraction.

## Reference, Citation, and Internal Link Policy

### Current Behavior

- bibliography sections are removed
- inline citation text is generally preserved in body text
- `.ltx_ref` links are unwrapped

### New Policy Surface

Introduce explicit options with stable semantics:

- `remove_refs`
  - if `true`, drop bibliography/reference sections from output
  - if `false`, allow them through if the caller explicitly wants them

- `remove_inline_citations`
  - if `true`, remove inline citation text generated from `ltx_cite`
  - if `false`, preserve citation text while stripping or simplifying links

- `remove_internal_links`
  - if `true`, convert internal paper links to plain text
  - if `false`, preserve them where Markdown rendering can support them

### Default Behavior

Default behavior in Paper Distill should remain conservative and close to today's pipeline:

- references removed
- inline citation text preserved unless explicitly disabled
- internal paper links simplified

### Why Borrow `arxiv2md` Here

`arxiv2md` already has clearer citation semantics at the serializer level. That logic should be adapted so citation handling becomes an explicit configuration concern instead of an accidental side effect of DOM cleanup.

## Section Title Normalization and Filtering

Introduce a shared title normalization layer modeled after `arxiv2md/sections.py`.

This layer will:

- normalize numbering variants like `1 Introduction`, `I. Introduction`, `A.1 Appendix`
- support reusable include/exclude filtering by logical title
- centralize detection of:
  - abstract
  - references / bibliography
  - appendix
  - future section buckets

### Internal Uses

This is not only for user-facing filters. Paper Distill should also use normalized titles internally to:

- identify appendix sections more robustly
- avoid brittle `re.search` duplication in multiple places
- improve section bucketing for downstream notes

## Appendix Policy

Replace the current binary-feeling behavior with an explicit appendix mode:

- `full`
  - keep appendix content in the main Markdown output
  - still extract appendix structure when possible

- `summary`
  - keep only an appendix snapshot summary in Markdown output
  - omit full appendix body from the main narrative

- `drop`
  - omit appendix content from main Markdown and appendix snapshots

### Default

`summary` remains the default because it matches Paper Distill's current token-control goals.

### Why Not Copy `arxiv2md` Default

`arxiv2md` treats appendix as ordinary content because its product goal is complete Markdown conversion. Paper Distill's goal is source distillation for downstream compilation, so appendix needs a stricter policy layer.

## Module Refactor Plan

The refactor should proceed in the following order:

### Phase 1: Extract utilities without changing behavior

- create new fetch, filter, parser, and serializer modules
- move existing Paper Distill logic into these modules with minimal semantic change
- keep `server/arxiv_capture.py` as a facade

### Phase 2: Introduce native HTML fetch fallback

- implement native `arxiv.org/html` first, then `ar5iv`
- keep existing PDF fallback behavior unchanged

### Phase 3: Upgrade formula and table serialization

- integrate `arxiv2md` math and table logic
- ensure Markdown improves without changing sidecar schema

### Phase 4: Introduce section normalization and filter policy

- replace scattered title-matching logic with shared helpers
- use normalized matching for references and appendix

### Phase 5: Introduce configurable citation/reference/internal-link controls

- thread config options through `capture_arxiv_source` and any direct fetch helpers
- keep defaults backward-compatible

### Phase 6: Expand regression coverage

- add focused tests for new parser and serializer modules
- preserve current end-to-end tests

## Testing Strategy

### Existing Tests to Preserve

- `tests/test_arxiv_capture.py`
- `tests/test_paper_add.py`
- `tests/test_server_tools.py`

### New Unit Test Areas

- native HTML then `ar5iv` fetch fallback
- citation removal vs preservation
- internal link removal vs preservation
- section normalization edge cases
- include/exclude filtering
- `thead` / `tbody` / figure-wrapped table rendering
- MathML-to-LaTeX conversion
- appendix modes: `full`, `summary`, `drop`

### Regression Assertions

The migration is only acceptable if the following remain true:

- figure/table/equation counts still populate correctly
- raw source sidecars still contain structured extraction fields
- `build_crgp_dnl` still produces evidence labels such as `Equation Snapshot`, `Figure Snapshot`, and `Table Snapshot`
- ingestion still succeeds through PDF fallback when HTML capture fails

## Risks and Mitigations

### Risk: Markdown quality improves but structured evidence regresses

Mitigation:

- keep the adapter layer explicit
- test structured fields independently from Markdown body output

### Risk: Section normalization changes downstream bucketing unexpectedly

Mitigation:

- add normalization unit tests
- keep bucket heuristics stable until explicit improvements are tested

### Risk: New citation flags silently change note content

Mitigation:

- preserve current defaults
- add direct tests for each flag combination that matters

### Risk: Refactor grows too large

Mitigation:

- split into phases with behavior-preserving extraction first
- do not combine module split and semantic upgrades in one commit

## Assumptions

- Paper Distill should remain local-first and should not call external `arxiv2md.org` APIs
- direct reuse of selected `arxiv2md` code is allowed under its MIT license with repository-local adaptation
- preserving downstream compatibility is more important than perfect parity with `arxiv2md`

## Success Criteria

The design is successful when:

- capture still returns a valid `CleanedArxivDocument`
- HTML capture works against native arXiv HTML and still falls back to `ar5iv`
- table Markdown becomes more faithful on realistic arXiv HTML
- equation Markdown becomes more legible while structured equation extraction remains intact
- citation/reference behavior becomes explicitly configurable
- appendix handling becomes policy-driven instead of hardcoded
- `server/arxiv_capture.py` becomes thinner and easier to reason about
