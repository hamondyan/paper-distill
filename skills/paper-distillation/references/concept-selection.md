# Concept Selection for Paper Pages

A paper page's `key_concepts_topk` is the topical index card for the paper. It has to carry one to five entries, and at least one must be wikilinked in the body. The selection rules below produce pages that actually fit into the concept graph instead of creating orphans.

## Target count

- Prefer one to three entries. Five is the absolute maximum and signals the paper is probably cross-cutting.
- If you cannot name at least one concept, the evidence is too shallow to distill. Stop and flag the capture quality.

## Selection algorithm

1. List the noun phrases that carry the paper's core claim. These are the candidate concepts.
2. For each candidate, call `check_concept_alias(name=<candidate>)`.
   - If the tool returns a canonical match, use that canonical surface.
   - If the tool returns no match, check whether the concept meets the "create concept page" bar (three or more future papers would link to it, stable literature name, reading-room useful).
   - If the concept does not meet the bar, pick a related but more canonical concept that does. Do not bloat the vault with one-off concept pages.
3. Drop candidates that are proper nouns for the paper itself (project names, dataset codenames) — those belong on the paper page, not the concept graph.
4. Drop candidates that only appear in the abstract but are not the paper's contribution — those are background, not key concepts.

## Creating a new concept page

If a selected concept has no existing page and clears the bar above, create the concept page in a follow-up `upsert_wiki_page(page_type="concept", ...)` call after the paper page lands. Required concept-page fields:

- `concept` — canonical surface.
- `aliases` — list of variant surfaces seen in the literature.
- `source_layer` — typically `wiki`.
- `related_papers_topk` — at least one supporting paper. Add the paper you just wrote.

Do not create two concept pages in the same session for unrelated ideas — concept creation is a deliberate act; batch creation tends to produce low-quality pages.

## Body linking rule

Every concept in `key_concepts_topk` must appear as `[[Concept Name]]` at least once in the body. The cleanest way is:

- Link each concept the first time it appears in prose.
- If a concept is listed but has no natural prose placement, add a one-line `Relations` bullet pointing at it.

The write-time validator rejects pages where no concept from `key_concepts_topk` is linked in the body.

## Common selection mistakes

- **Laundry list**: picking every noun phrase from the abstract. Two strong concepts beat five weak ones.
- **Proper-noun concepts**: picking the paper's own project name as a concept. Those belong on the paper page title, not on the concept graph.
- **Generic fallback**: picking "deep learning" or "transformer" for a paper where the specific mechanism is much narrower. Pick the narrowest concept that is still reusable.
