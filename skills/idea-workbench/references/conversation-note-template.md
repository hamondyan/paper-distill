# Conversation Note Template

Conversation notes live at `insights/conversations/<slug>.md` and are written through `upsert_wiki_page(page_type="conversation", ...)`. Never create or edit them by hand. Never store verbatim chat transcripts.

## When this note is the right asset

Use a conversation note when the durable takeaway is a reusable observation, preference, or cross-paper lesson that is not a research hypothesis. If the takeaway is a testable idea, use the idea note template instead. If the takeaway is a fact about a single paper, put it on the paper page.

## Frontmatter

```yaml
source_layer: insights
related_concepts_topk: [<up to three canonical concept surfaces>]
```

Normalize every entry in `related_concepts_topk` via `check_concept_alias` before writing.

## Slug rules

- Phrase the slug as the insight itself, not the conversation topic.
- Good: `diffusion-policies-need-analytical-guarantee`, `ablations-rarely-isolate-perception`.
- Avoid: `chat-2026-04-18`, `user-asked-about-diffusion`.

## Body sections

### Insight

One paragraph, 2–4 sentences. State the takeaway as if writing a note for a future reader who does not remember the conversation.

### Evidence

Bulleted references to the paper or concept pages that grounded the insight. Name each page and the specific contribution that supported the observation.

### Applies To

Describe when this insight should change the agent's future behavior. Be specific about the trigger: "When the user proposes diffusion-based control without an analytical component…", "When discovering survey papers in this subfield…".

### Limits

Where this insight does not apply. Without explicit limits, a conversation note tends to overreach and silently narrow the agent's behavior on unrelated tasks.

## What never goes in

- The user's literal messages.
- The agent's reasoning traces.
- Search results or tool output longer than a single line.

## Length

Keep a conversation note under 30 lines of body text. If the insight needs more, it is probably a concept page plus an idea note waiting to be extracted.
