# Troubleshooting

Common problems organized by symptom.

---

## Setup

### "VAULT_PATH not configured" or vault operations fail

**Symptoms:** Tools return errors mentioning vault path, `bootstrap-library` fails, paths are empty.

**Fix:**
1. Set `paper_distill.vault_path` in `settings.json`:
   ```json
   { "paper_distill": { "vault_path": "/absolute/path/to/vault" } }
   ```
2. Or set the `VAULT_PATH` environment variable:
   ```bash
   export VAULT_PATH=/absolute/path/to/vault
   ```
3. Run `bootstrap-library` once to create the directory structure.

---

### Server fails to start with ImportError

**Symptom:** Python import error when starting the MCP server.

**Fix:**
1. Ensure dependencies are installed: `uv sync` or `pip install -e .`
2. Check that all `server/` sub-modules exist: `paper_scoring.py`, `paper_frontmatter.py`, `capture_settings.py`, `paper_identity.py`, `discovery_helpers.py`, `ingestion_helpers.py`.
3. Verify entry point: `uv run python server/server.py` should start without errors.

---

## Discovery

### source-discover returns 0 candidates

**Symptoms:** Tool completes but `candidates` list is empty.

**Checks:**
1. Verify `paper_distill.search.sources` is not empty in `settings.json`.
2. Check that `paper_distill.topics` has at least one entry with non-empty `keywords`.
3. If using `topic_keys` parameter, confirm those keys exist in `settings.json`.
4. The `require_arxiv_binding` workflow setting (default: `true`) will filter out papers without arXiv IDs — try disabling it temporarily.

### Discovery results are off-topic

**Symptom:** Returned candidates do not match your research area.

**Fix:**
1. Add `must_include` terms to the topic definition to narrow results:
   ```json
   "my-topic": {
     "keywords": ["robot", "manipulation"],
     "must_include": ["robot"],
     "must_exclude": ["medical", "surgery"]
   }
   ```
2. Add rejected keywords via `update_learned_preferences(rejected_keywords=[...])`.
3. Inspect `drift_warnings` in the tool response — it will suggest exclude terms.

---

## Ingestion

### source-ingest returns 0 items processed (approved_inbox mode)

**Symptom:** Running `/process-inbox` does nothing.

**Fix:**
1. Call `query-library(section="inbox", status="approved")` to confirm there are approved items.
2. Verify inbox notes have `status: approved` in their YAML frontmatter (not `proposed`, `rejected`, or `deferred`).
3. Check that `status` property is the first line under `---` — some Obsidian versions are picky about YAML ordering.

### ar5iv capture failed / capture fidelity is "low"

**Symptom:** `capture_fidelity: low` in source evidence, or capture logs show ar5iv failure.

**Explanation:** Paper Distill tries ar5iv HTML first, then falls back to PDF text extraction. "low" fidelity means only PDF text was recovered.

**Checks:**
1. Confirm the paper has an arXiv ID — ar5iv only works for arXiv papers.
2. ar5iv may have a processing delay for very recent papers (within 24 hours of submission).
3. Lower `capture.min_body_chars` in `settings.json` if PDF extraction is consistently below threshold:
   ```json
   "capture": { "min_body_chars": 800 }
   ```
4. Check if the paper is open access — `fetch_pdf_text` requires a downloadable URL.

### Zotero handoff fails silently

**Symptom:** `zotero_status: error` in source evidence, but no clear error message.

**Fix:**
1. Check `zotero.mode` in `settings.json` — use `disabled` if you don't need Zotero.
2. For `local_first` mode: verify the export directory is writable and Obsidian can see it.
3. For `web_api` mode: confirm `ZOTERO_LIBRARY_ID` and `ZOTERO_API_KEY` env vars are set and valid.

---

## Compilation

### knowledge-compile-status shows manual_edit_conflict: true

**Symptom:** `knowledge-compile-publish` returns `manual_edit_conflict: true`, compilation stops.

**Explanation:** The wiki file was edited by hand after the last compile. The `content_hash` no longer matches.

**Fix:**
1. Read the current file to review your manual changes.
2. Copy any manual sections you want to keep (e.g., `## My Notes`).
3. Re-run the EDC pipeline: Extract → Resolve → Write.
4. In the Write step, append your preserved manual sections to the generated content **before** calling `knowledge-compile-publish`.

### paper-distill-extract returns validation errors

**Symptom:** IR submission fails with field validation errors.

**Fix:** The IR must include all required fields. Most common omissions:
- `tension_fields` must have all four keys: `limitations`, `assumptions`, `open_questions`, `negative_results` (empty lists `[]` are valid).
- `candidate_concepts` items must have `surface_form`.
- `citekey` must match the source evidence file exactly.

See [Compile IR Schema](compile-ir-schema.md) for the full schema.

### knowledge-compile-resolve shows 0 concepts resolved

**Symptom:** Resolve stage completes but `concepts_resolved: 0`.

**Checks:**
1. Verify the raw IR file exists at `.state/ir/{citekey}.json`.
2. Confirm `candidate_concepts` in the IR is not empty.
3. Run `list_concepts_tool()` to check if the registry is populated — if empty, run `backfill_registry` first.

---

## Concept Registry

### Concept is registered but no wiki stub page exists

**Explanation:** This is expected behavior. The registry entry is a bookkeeping record; the wiki stub is an editorial artifact.

**Rule:** Create a `wiki/concepts/{slug}.md` stub only after `list_concepts_tool(min_paper_count=2)` confirms the concept appears in at least two papers (the "two-paper rule").

### Auto-merge is not triggering for abbreviations

**Symptom:** `VLA` and `vision-language-action` are not being merged automatically.

**Fix:** Check `concept_registry.abbreviation_whitelist` in `settings.json`. The entry should be:
```json
"concept_registry": {
  "abbreviation_whitelist": {
    "vla": "vision-language-action"
  }
}
```
Keys and values are slug-normalized, so `"VLA"` and `"vla"` are equivalent.

---

## Library Queries

### query-library returns provider: filesystem_scan

**Symptom:** Tool works but `provider` field is `"filesystem_scan"` instead of `"obsidian_cli"`.

**Explanation:** The Obsidian CLI adapter is not active. This happens when:
- Obsidian is not open, or the open vault does not match `vault_path`.
- The Obsidian Local REST API or similar plugin is not running.

**Impact:** `filesystem_scan` returns the same data via direct frontmatter parsing. All features work; only performance and advanced Obsidian query features are affected.

**Fix:** Open the vault in Obsidian, ensure the query plugin is running, and retry. See [Obsidian CLI Validation](obsidian-cli-validation.md) for the full capability matrix.

### query-library returns stale or missing papers

**Symptom:** Papers exist on disk but do not appear in query results.

**Fix:**
1. Run `wiki-lint` to identify structural issues (broken frontmatter, missing required fields).
2. Ensure the paper's YAML frontmatter contains the expected `type` field.
3. Try `detail="full"` to see raw frontmatter for debugging.

---

## Maintenance

### reconcile_maintenance creates duplicate tasks

**Symptom:** Running `reconcile_maintenance` twice creates duplicate entries.

**Fix:** `reconcile_maintenance` is designed to be idempotent — it deduplicates tasks by payload hash. If duplicates appear, run `get_maintenance_queue(status="pending")` and `resolve_maintenance_task(task_id, action="reject")` for the duplicates.

### execute_maintenance_task fails with "task not confirmed"

**Symptom:** Task execution fails because task status is `pending`.

**Fix:** Tasks must be in `confirmed` status before execution.
1. Call `resolve_maintenance_task(task_id, action="confirm")` first.
2. Or re-run `reconcile_maintenance(auto_confirm=true)` to auto-confirm qualifying tasks.
