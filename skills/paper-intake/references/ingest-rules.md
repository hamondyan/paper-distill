# Ingest Rules — Detail

`ingest_and_read(input_value=<identifier_or_batch>)` accepts one or many arXiv URLs, arXiv IDs, or arXiv DOI values in a single call.

## Natural reference resolution

Natural references — titles, project names, acronyms, aliases — must be resolved by the agent to arXiv URLs, IDs, or DOI values before the MCP call. The MCP tool itself does not search arbitrary strings.

- If the agent cannot find a credible resolved identity for a reference, treat it as unresolved and do not include it in the tool call.
- Do not ask the user to confirm agent-resolved arXiv URLs, IDs, or DOI values before calling `ingest_and_read`. Resolution confidence is part of the agent's job.

## Reporting contract

After a capture round, report:

- **Resolved inputs** — the arXiv identities that were passed to the tool.
- **Unresolved inputs** — natural references the agent could not map with confidence.
- **For each captured paper**: `paper_id`, title, raw evidence path, and any errors.
- **Warnings**: if capture succeeds but later processing reports a warning (e.g. short body, missing sections), keep the successful file write and surface the warning in the report.
- **Concept compounding failures**: if post-capture concept compounding fails, report it clearly. The new paper still enters the vault even if concept side effects did not.

## Capture invariants

- `raw/evidence/` is normally read-only after capture. Capture repair (e.g. re-ingesting the same `paper_id` with better HTML) may rewrite the same file, but agents must never edit captured evidence by hand.
- A capture write includes a frontmatter `content_hash` (SHA-256 of the body) so later reads can detect tampering.

## Post-ingest follow-up

After write-heavy work, QMD refresh is a separate follow-up step rather than implicit.

- Recommend `qmd update` after the current write round.
- Recommend `qmd embed -f` if semantic retrieval must reflect the new state immediately.

## Mixed direct intake

When a single user request mixes resolved arXiv inputs with unresolved natural references, report the two groups separately so the user can see which items will be captured and which names need another lookup round.
