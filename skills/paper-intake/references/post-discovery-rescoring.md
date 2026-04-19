# Post-Discovery Re-scoring Playbook

The `discover_papers` tool uses a pure heuristic scorer: topic_fit, recency, novelty, impact, venue tier, author preference, metadata quality, profile alignment, taste alignment. When a user's research direction is narrow or uses non-standard terminology, heuristic matches miss papers that are semantically relevant but do not share keywords with the configured topics.

The agent fills that gap after `discover_papers` returns, before presenting candidates to the user.

## When to run

After every `discover_papers` call, scan the returned `results` for candidates where both:

- `score` is 0 or 1, and
- the candidate has `topic_fit: 0` when that field is present.

These are the candidates most likely to be rescuable by semantic judgement.

## What to do

For each candidate matching the criteria above:

1. Read the returned abstract, source URL, and extracted metadata.
2. Compare against the user's `research_profile.direction` (from `settings.json`) and any seed papers or whitelisted authors.
3. Decide: relevant, tangential, or off-topic.

## How to present the result

- **Relevant**: promote the candidate in the chat summary with one concise reason. Keep the reason under 120 characters.
- **Tangential or off-topic**: leave the candidate at its original rank or omit it from the short recommendation set.

Do not modify files during this pass. Do not change `score`, `topic_fit`, or any scoring-layer field in the returned result — that namespace belongs to the MCP tool.

## Bounding the pass

- Cap the re-scoring pass at 20 candidates per discovery round to avoid runaway token cost.
- If a discovery round surfaces more than 20 zero-score candidates, pick the most recently published first.
- If the user's direction is broad enough that most candidates already have non-zero scores, skip the pass entirely.

## Reporting

When recommending papers to the user after a discovery round, annotate agent-promoted candidates so the user understands the basis for the recommendation (heuristic score vs. agent-side semantic judgement).
