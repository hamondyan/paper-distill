# Health And Index Maintenance — Detail

`lint_vault` reports structural issues without rewriting files. Use it to decide what to clean up; use QMD CLI operations to keep the retrieval index fresh.

## Common lint issue codes

- `dead_link` — a wikilink whose target file does not exist. Fix by creating the target, removing the link, or pointing at the correct canonical surface.
- `malformed_link` — a wikilink with broken delimiters or an empty target. Fix by rewriting the link.
- `alias_ambiguity` — a link target resolves to more than one concept page via `aliases`. Decide on the canonical concept with `check_concept_alias` and call `merge_concept` or rewrite the links.
- `repeated_link` — the same wikilink is repeated in one paragraph block. Usually a template-fill accident; remove duplicates.
- `template_footer_link` — a page ends with a boilerplate "related reading" block that links everything. Rewrite the footer into prose with at most three intentional links.
- `frontmatter_too_large` — frontmatter exceeds the threshold. Move narrative fields into the body.
- `paper_missing_required_fields` — a paper page is missing required metadata such as `year`, `venue`, `source_layer`, or `key_concepts_topk`. Fill the metadata before doing cosmetic cleanup.
- `paper_missing_concept_link` — a paper page does not link any known concept in the body. Add at least one intentional concept link.
- `paper_key_concept_unlinked` — the page links concepts, but none of them match `key_concepts_topk`. Either fix the body links or change the frontmatter list.
- `paper_too_many_concept_links` — a paper page links more than five concepts. Keep the important ones and turn the rest into prose.
- `concept_missing_supporting_paper` — a concept page has no `related_papers_topk`. Add at least one supporting paper or delete the page.
- `paper_without_raw_evidence` — a canonical paper page has no matching `raw/evidence/` file for its `paper_id`. Repair the capture trail before treating the page as canonical.

## When to run `qmd update`

After any round of writes (paper, concept, idea, conversation), the new or changed pages are not yet in the retrieval index. Run `qmd update` to pick them up. If you are in a long session with many write operations, run `qmd update` once at the end rather than after each write.

## When to run `qmd embed -f`

Run `qmd embed -f` when semantic retrieval must reflect the new state immediately — for example, when the next step is a `qmd query` over concepts that were just created or renamed. Skip it otherwise; embedding is the more expensive half of the index refresh.

## Triage heuristic

When `lint_vault` returns many issues:

1. Group by issue code and report counts first, not a wall of paths.
2. Fix schema-level issues (paper missing fields, concept missing supporting papers) before cosmetic ones (dense links, template footers).
3. Do not auto-fix from this skill. Propose a concrete change, let the user approve, then call the write tool.
