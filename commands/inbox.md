---
name: inbox
description: Show inbox candidates and approval instructions
user_invocable: true
---

Summarize the current inbox, including how many files are present and which ones already contain `#approved` in the note body.
Explain that approval is performed by adding `#approved` to the note body.
Show the approval rule clearly:

```markdown
Review notes here.

#approved
```

Only a plain body tag counts. A frontmatter field, blockquote, inline code span, or fenced code block containing `#approved` does not approve the note.
Do not ingest anything from this command.
If the user asks how to read or search existing vault knowledge, point them to `docs/qmd-cli.md` and QMD CLI rather than retired wrapper commands.
