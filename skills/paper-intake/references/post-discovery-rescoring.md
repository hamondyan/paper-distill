# Post-Discovery Re-scoring Playbook

The `discover_papers` tool uses a pure heuristic scorer: topic_fit, recency, novelty, impact, venue tier, author preference, metadata quality, profile alignment, taste alignment. When a user's research direction is narrow or uses non-standard terminology, heuristic matches miss papers that are semantically relevant but do not share keywords with the configured topics.

The agent fills that gap after `discover_papers` returns, before recommending candidates to the user.

## When to run

After every `discover_papers` call, scan the just-written inbox stubs for candidates where both:

- `score` is 0 or 1, and
- the stub has `topic_fit: 0` (keyword matching missed the paper entirely).

These are the candidates most likely to be rescuable by semantic judgement.

## What to do

For each candidate matching the criteria above:

1. Read the stub body (abstract + source URL + any extracted metadata).
2. Compare against the user's `research_profile.direction` (from `settings.json`) and any seed papers or whitelisted authors.
3. Decide: relevant, tangential, or off-topic.

## How to mark the result

- **Relevant**: add a one-line `rescore_reason` to the inbox note body, just above the abstract section. Format: `rescore_reason: <concise why the paper fits the direction>`. Keep it under 120 characters. Future recommendation rounds treat stubs with this marker as promoted candidates regardless of numeric score.
- **Tangential or off-topic**: do nothing. The stub stays with its heuristic score and will not surface in recommendations unless the user explicitly asks.

Do not modify any other inbox frontmatter or body section during re-scoring. Do not touch `score`, `topic_fit`, or any scoring-layer field — that namespace belongs to the MCP tool.

## Bounding the pass

- Cap the re-scoring pass at 20 stubs per discovery round to avoid runaway token cost.
- If a discovery round surfaces more than 20 zero-score candidates, pick the most recently published first.
- If the user's direction is broad enough that most candidates already have non-zero scores, skip the pass entirely.

## Reporting

When recommending papers to the user after a discovery round, annotate any candidate that received a `rescore_reason` so the user understands the basis for the recommendation (heuristic score vs. agent-side semantic judgement).
