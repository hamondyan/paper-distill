---
name: status
description: Use when the user wants a vault health snapshot: page counts, recent activity, and outstanding lint issues.
argument-hint: ""
user-invocable: true
---

Produce a concise vault health snapshot for the user. This is an agent-side command; no new MCP tool is required.

Gather the snapshot from the following sources:

1. Call `lint_vault` for the current issue list (group by issue code in the summary).
2. Count files with QMD CLI or a filesystem scan:
   - `wiki/papers/*.md` - canonical papers
   - `wiki/concepts/*.md` - canonical concepts
   - `insights/ideas/*.md` - active ideas
   - `insights/conversations/*.md` - distilled conversation notes
   - `raw/evidence/*.md` - captured evidence files
3. Read the tail of `vault-log.md` for the most recent ingest and write operations.

Report shape (keep it short, one screen):

- **Counts**: papers, concepts, ideas, conversations, raw evidence
- **Lint issues**: top codes with counts; flag any `paper_missing_required_fields`, `paper_missing_concept_link`, `paper_key_concept_unlinked`, or `paper_without_raw_evidence` explicitly
- **Recent activity**: last 3-5 vault-log entries
- **Suggested next action**: based on the biggest gap in capture, distillation, lint, or index freshness.

Do not rewrite files from this command. If the user wants the lint issues fixed, point to the relevant skill or workflow (for example paper-distillation for schema gaps).
