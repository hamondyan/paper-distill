# Query Recipes

`qmd query` is hybrid by default. These recipes cover the cases where that default is not what you want, or where a filter changes the answer.

## Default: plain hybrid query

```bash
qmd query "diffusion scaling law"
qmd query "vision-language-action policy open-source"
```

Use a single-line natural-language string. The retriever does lexical + vector + rerank under the hood. This is the first thing to try for almost every question.

## Typed query document

If every line is prefixed with `lex:`, `vec:`, or `hyde:`, QMD treats the whole input as a typed query. Useful when a plain hybrid search drifts off-topic and you want to steer it.

```bash
qmd query $'lex: "transformer"\nvec: retrieval augmentation'
qmd query $'hyde: describe a paper that uses diffusion to generate robot trajectories\nlex: "diffusion policy"'
```

Rules:

- Do not mix a plain query and typed lines in one invocation. Pick one mode.
- `lex:` is BM25-style keyword search.
- `vec:` is semantic embedding search.
- `hyde:` synthesizes a hypothetical answer and retrieves against it — useful when the user's query uses different vocabulary than the corpus.

## Collection filters

Use `-c <collection>` when the user has asked about a specific layer.

```bash
qmd query "concept merge rationale" -c canon-concepts
qmd query "robot manipulation benchmark" -c canon-papers
qmd query "open questions from last week" -c insights-conversations
```

Pick the collection from the repo handle list in [../SKILL.md](../SKILL.md):

- `canon-papers`, `canon-concepts` → when the user wants distilled vault content
- `raw-evidence` → when the user is asking about captured evidence, not the distilled page
- `insights-conversations`, `insights-ideas` → when the user is mining their own prior synthesis

## Lexical-only fallbacks

If hybrid keeps returning semantically similar but wrong-topic results, drop to lexical:

```bash
qmd search "OpenVLA"
qmd vsearch "diffusion policy for manipulation"
```

`qmd search` is BM25 only; `qmd vsearch` is vector only. These are appendix commands — reach for them only when `qmd query` is visibly mis-ranking.

## Slicing results

`qmd query` returns snippets; once a candidate looks right, switch to `qmd get` to read the whole page or a slice:

```bash
qmd get wiki/papers/openvla.md
qmd get wiki/papers/openvla.md:1 -l 80
```

Avoid round-tripping the user through multiple `qmd query` calls when they have already pointed at a file.
