# Concept Rules — Detail

Concept pages are the backbone of the vault's topical index. They let QMD retrieval return a topic rather than a single paper, and they let paper pages cross-link without duplicating prose. Treat the concept namespace as scarce: only core concepts deserve pages.

## When to create a concept page

Create a concept page when all of the following are true:

- Three or more existing papers would legitimately link to this concept in their `key_concepts_topk`.
- The concept has a stable canonical name in the literature (not a single author's neologism).
- The concept is useful at the reading-room level — it would help a user recall what a cluster of papers has in common.

Do not create a concept page for:

- One-off project names (use paper pages instead).
- Sub-methods embedded in a single paper (link to the paper).
- Organizational groupings like "2024 papers" or "NeurIPS" (let search filters handle this).

## Naming

- Use the literature's canonical surface. If the literature is split, pick the most widely cited phrasing and list variants in `aliases`.
- Prefer singular noun phrases: "Diffusion Policy", not "Diffusion Policies".
- Keep the casing natural — do not force Title Case if the literature uses lowercase (e.g. "transformer" is fine).

## Using `check_concept_alias`

Before creating a concept or linking to one from a paper page, call `check_concept_alias(name=...)` with every plausible surface (the term as it appears in the paper, the acronym, any synonyms). If the tool returns a canonical match, link to that canonical page. If it returns no match and the concept meets the "when to create" bar, create a new concept page.

## When to merge

Call `merge_concept(old=..., new=...)` when:

- Two concept pages clearly describe the same thing and you can pick which canonical surface to keep.
- A concept drifts over time and the vault now has both the old and new names as separate pages.

After a merge, report:

- The files whose wikilinks were rewritten.
- Whether the `old` surface was added to the target's `aliases` list.
- The suggestion to run `qmd update` and, if retrieval must immediately reflect the change, `qmd embed -f`.

## Key concepts on paper pages

A paper page's `key_concepts_topk` carries one to five entries. Pick the smallest useful set: one to three is preferred, five is the cap. Every listed concept must be wikilinked in the paper body at least once. If a concept is important enough for the list but does not need inline discussion, add a single "Relations" line that links it.
