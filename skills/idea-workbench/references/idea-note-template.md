# Idea Note Template

Idea notes live at `insights/ideas/<slug>.md` and are written through `upsert_wiki_page(page_type="idea", ...)`. Never create or edit them by hand.

## Frontmatter

```yaml
idea_state: active          # active | parked | rejected | superseded
topics: [<up to three topic tags>]
related_papers: [<paper wikilinks or paper_ids>]
related_concepts: [<canonical concept surfaces>]
# Optional fields once the idea state is no longer active:
# decision_reason: <one-line why the state changed>
# decision_at: <ISO date>
# superseded_by: <slug of the idea that replaced it>
```

Use `check_concept_alias` on every entry in `related_concepts` before writing, so the idea page links to canonical surfaces.

## Slug rules

- Short, specific, imperative or declarative noun phrase.
- Good: `perception-scaffold-before-action`, `ablate-diffusion-with-frozen-backbone`.
- Avoid: `idea-2026-04-18`, `new-thing`, generic project codenames.

## Body sections

Use these five sections, in this order. Omit any that would be empty; do not invent filler.

### Summary

One paragraph, 3–5 sentences. What is the idea, what is the one-line why.

### Local Evidence

Bulleted references to the vault: paper wikilinks and concept wikilinks that motivated or constrain the idea. Every bullet should name a specific page and a specific contribution from it.

### Hypothesis / Bridge

The testable statement. Prefer the shape "If X, then Y, measured by Z." Call out the bridge between the evidence and the prediction.

### Kill Criteria

At least one concrete condition under which the idea dies. Without a kill criterion, the idea stays as `idea_state: active` indefinitely and the vault accumulates stale optimism.

### Next Step

One concrete action, sized to a single session. Examples: "read [[Paper]] and check if the proposed metric applies", "prototype the single-module ablation", "ask <collaborator> whether dataset <X> is licensable".

## Length

Keep an idea note under 60 lines of body text. If it needs more, it is probably two ideas or an early conversation insight.
