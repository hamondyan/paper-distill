# Writing Style for Canonical Paper Pages

Existing canonical pages in this vault (OpenVLA, RT-1, DNAct, Abstract 3D Perception) are the benchmark. Before writing a new page, open one of those pages with `qmd get` to see how the sections flow.

## Section order

```markdown
## One-liner

<Single sentence, 20–30 words. What does the paper do and why is it notable?>

## Problem

<One short paragraph. See references/extraction-template.md question 1.>

## Core Idea

<One paragraph, technical. The mechanism, not the marketing.>

## Contributions

- <Three to five bullets.>

## Data and Setup

<Short paragraph or bullets. Include quantities.>

## Results

<Short paragraph or bullets with the specific delta against the closest prior work.>

## Novelty

<One paragraph naming the nearest prior works and the specific delta.>

## Limitations

<One paragraph. Honest, specific, not boilerplate.>

## Relations

- [[Other paper]] — one-line connection.
- [[Concept]] — one-line why it matters here.

## Impact

<Optional. One paragraph. Skip if you cannot ground impact in the evidence.>
```

## Prose rules

- Write in declarative sentences. Avoid hedges ("arguably", "it seems") and avoid superlatives that the evidence does not support.
- Use wikilinks in the first occurrence of a concept, not every occurrence. Dense linking is a lint issue.
- Quote specific numbers from the paper when they are load-bearing. A page that says "large performance gain" ages badly; a page that says "+9.4 points on LIBERO-goal" does not.
- Do not paraphrase the abstract. The abstract is in the raw evidence; the page must add structure and context the abstract lacks.

## Length

Aim for 40–70 lines of body prose after the required sections. Longer pages are usually padded; shorter pages usually skip a section.

## Cross-links

- Use `[[Paper Title]]` for paper-to-paper links. Match the canonical title surface of the target paper page.
- Use `[[Concept Name]]` for concept-to-concept links.
- If a link target does not exist yet, either create it or rewrite the sentence to avoid the dangling link. Dangling wikilinks are a lint issue.

## Anti-patterns

- Ending with a boilerplate "Related Reading" block that links six other papers without explaining why. Keep `Relations` terse and specific.
- Using the same concept wikilink five times in one page. Link once; use prose for the rest.
- Restating the paper's own title in the one-liner ("`OpenVLA` is an open-source vision-language-action model…"). The page already has the title — the one-liner should add information.
