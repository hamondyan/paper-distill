# Idea Curation Rules

Ideas decay. A well-curated `insights/ideas/` folder shows at most a handful of active ideas, each with a clear next step and a kill criterion. Everything else is parked, rejected, or superseded — still readable, but clearly not on the critical path.

## State transitions

An idea note's `idea_state` is one of:

- `active` — the idea is being evaluated or pursued. Must have a next step and at least one kill criterion.
- `parked` — the idea is on hold because a prerequisite is missing (dataset, collaborator, capability). Must record `decision_reason` and ideally the unblocking condition.
- `rejected` — the idea is killed. Must record `decision_reason` (the observation that triggered the kill) and `decision_at`.
- `superseded` — a better framing replaced it. Must record `superseded_by` pointing at the replacement slug.

Transitions always move forward: `active → parked`, `active → rejected`, `active → superseded`, `parked → active`, `parked → rejected`. Do not quietly flip `rejected` back to `active`; instead write a new idea that cites the rejected one in `Local Evidence`.

## Ranking active ideas

When the user asks "what should I work on?", rank active ideas by these, in order:

1. **Evidence strength** — how many independent paper pages support the hypothesis. Three or more is strong; one is speculative.
2. **Novelty** — whether a `qmd query` on the hypothesis returns existing papers that already did the work. If yes, downgrade or reject.
3. **Feasibility** — whether the next step is executable in one session. If the next step is "build a benchmark from scratch", the idea is not ready.
4. **Kill-criterion clarity** — a sharp, measurable kill condition ranks above a vague one.

Do not rank by how interesting the idea feels. Interestingness without evidence is a flag to go read more, not to promote the idea.

## Cleanup passes

Every 20 ideas or every two weeks of use, the user can ask for a curation sweep. The sweep should:

- Identify `active` ideas whose next step has stalled. Propose `parked` with a reason.
- Identify ideas whose evidence bullets are all older than the state of the field. Propose `superseded` with a link to the candidate replacement.
- Consolidate ideas that now obviously overlap. Propose `superseded` on the weaker one.

Propose — do not auto-rewrite. The user decides; the agent then calls `upsert_wiki_page` to apply the state changes.

## Retirement

Do not delete rejected or superseded idea notes. The negative knowledge (why the idea did not work, what replaced it) is the point. Retain them so future similar proposals can be identified and routed to the prior conclusion.

## Proactive triggers

After a batch distillation (two or more papers in one session), proactively propose two or three candidate ideas grounded in the new evidence. See the Insights Triggers section of [../../../CLAUDE.md](../../../CLAUDE.md). Propose; do not auto-write.

