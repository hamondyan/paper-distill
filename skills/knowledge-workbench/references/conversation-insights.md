# Conversation Insights — Detail

A conversation insight is a short, reusable takeaway that emerged from a chat session and that would be useful to the user in a future unrelated conversation. It is not a transcript and not a task log. If removing the note would not lose durable knowledge, do not write it.

## When to capture

Capture when the session produced one of the following:

- A cross-paper observation (e.g. "two competing strands on the same problem differ mainly in the inference-time constraint").
- A methodological lesson (e.g. "ablations in this subfield rarely isolate the perception component from the policy").
- A research taste update (e.g. "user rejected diffusion-heavy papers unless they include an analytical guarantee").
- A negative result the user wants to remember (e.g. "tried concept X as an integrator, it did not help — do not propose it again without evidence").

Do not capture:

- Chat pleasantries, status updates, or re-statements of what the agent just did.
- Information already recorded on a paper page or concept page.
- Raw search results, lint outputs, or counts.

## Note structure

Write through `upsert_wiki_page(page_type="conversation", target=<slug>, frontmatter=..., body=...)` or the Python conversation insight writer.

Recommended frontmatter:

```yaml
source_layer: insights
related_concepts_topk: [<up to three canonical concept surfaces>]
```

Recommended body sections:

- `Insight` — one-paragraph statement of the takeaway.
- `Evidence` — the paper pages, concept pages, or conversation turns that grounded the insight.
- `Applies To` — when the insight should change future agent behavior.
- `Limits` — where the insight does not apply.

## Slugging

Slug the target as a short imperative or noun phrase: `diffusion-policies-need-analytical-guarantee`, `ablations-rarely-isolate-perception`. Avoid timestamps in the slug — those are better placed in frontmatter.

## What never goes in

- Verbatim transcripts of the user's messages.
- The agent's reasoning traces.
- Tool outputs longer than a single line.

If the insight seems to require more than a page of prose to state, it is probably a pair of concept or idea pages in disguise — convert it to structured assets instead.

## Proactive triggers

See the Insights Triggers section of [../../../CLAUDE.md](../../../CLAUDE.md) for when to offer a conversation note after distillation or batch work. Offer; do not auto-write.

