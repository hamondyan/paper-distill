# Approval Rules — Detail

Approval is a file-native operation. Only a plain `#approved` marker in the inbox note body makes the note eligible for capture by `ingest_and_read(input_value="approved")`.

## What counts

- A literal line or inline occurrence of `#approved` in the body, outside fenced code blocks and outside blockquotes.
- Written by the user directly in the note, or by `approve_papers` on the user's behalf after the agent resolves a chat-side selection.

## What does not count

- `#approved` inside a fenced code block, inline code span, or blockquote — ignored.
- A frontmatter field such as `status: approved` or `tags: [approved]` — ignored by design. Approval must be unambiguous, and frontmatter fields are too easy to set accidentally by templates.
- The filename containing the word "approved" — ignored.
- `#approved` in a helper/template note whose filename starts with an underscore (for example `_template.md`) — ignored by `approve_papers all`.

## Resolving chat selections

When a user conversationally approves papers after a discovery round:

1. Map the user's selection (paper title, arXiv ID, or positional reference like "the second one") to the paper IDs or inbox paths that were recommended in the same turn.
2. Batch the resolved identifiers into a single `approve_papers(input_value=...)` call when possible.
3. Report which notes received the marker and remind the user that `/ingest approved` is the capture step — approval alone does not write to `raw/evidence/`.

## Edge cases

- **Nested inbox folders**: `approve_papers` walks the full `inbox/` tree. Approved markers in nested notes (e.g. `inbox/2026-04-16/foo.md`) are respected.
- **Already-approved notes**: `approve_papers` is idempotent. Calling it on a note that already has `#approved` does not duplicate the marker.
- **All-or-none semantics**: `approve_papers(input_value="all")` approves every inbox note whose body lacks `#approved` and whose filename does not start with an underscore. It skips template helpers and already-approved notes silently.
