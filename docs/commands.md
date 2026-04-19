# Commands

Paper Distill v3.0 keeps slash commands for business actions only.

- `/discover` returns stateless, chat-only paper candidates.
- `/ingest <ref>` captures raw evidence from agent-resolved arXiv identities.
- `/lint` runs v3 health checks.
- `/status` returns a vault health snapshot (counts, lint issues, last activity).

Typical flow: discover -> ingest resolved arXiv references -> distill_paper -> qmd update -> lint.

In plugin hosts that namespace slash commands, these may appear with the plugin prefix, for example `/paper-distill:discover`.

Read/index tasks belong to QMD CLI. Use [docs/qmd-cli.md](qmd-cli.md) for `qmd query`, `qmd get`, `qmd status`, `qmd update`, `qmd embed -f`, collection/context checks, and `qmd ls`.

## Tool Mapping

- `/discover` -> `discover_papers`
- `/ingest` -> `ingest_and_read`
- `/lint` -> `lint_vault`
- `/status` -> agent-side snapshot (calls `lint_vault` + scans vault directories)

`distill_paper` and `distill_papers` are MCP workflow tools rather than slash commands. Use them after raw evidence exists and the agent has a distilled payload ready to write.

## Command Details

### `/discover`

Runs discovery using configured topics or a user-supplied query, scores candidates, and returns results directly to the agent for presentation in chat.

Discovery is stateless. It returns transient candidates, stores no selection state, and does not ingest papers. After discovery, the agent helps the user choose candidates from the current chat result and resolves chosen papers to arXiv URLs, IDs, or arXiv DOI values before capture.

### `/ingest`

Captures raw evidence for resolved arXiv papers.

The command receives resolved arXiv URLs, IDs, or arXiv DOI values. Natural paper names must be resolved by the agent before invoking `/ingest`; the MCP tool itself captures only resolved arXiv identities.

For mixed direct intake, report resolved arXiv inputs separately from unresolved user references. That makes it clear which papers were eligible for capture and which names still need lookup.

Examples:

```text
/ingest https://arxiv.org/abs/2410.24164
/ingest 10.48550/arxiv.2410.24164
/ingest 1706.03762
/ingest 10.48550/arxiv.2410.24164, 1706.03762
```

### Distill MCP Tools

Use `distill_paper(input_value, distilled?)` or `distill_papers(items)` when the user says "distill this paper" after capture.

Without a distilled payload, `distill_paper` resolves the raw evidence and returns a `needs_distillation_payload` response. After the agent reads the evidence and prepares grounded frontmatter/body content, call it again with `distilled.frontmatter`, `distilled.body`, and optional `distilled.target`.

### `/lint`

Runs `lint_vault` and reports structural issues without rewriting files. It checks malformed or dead links, alias ambiguity, repeated links, template-like footer linking, oversized frontmatter, paper pages missing required fields, paper pages missing concept links, paper key concepts not linked in the body, overly dense paper concept links, decorative concept links, concept pages without supporting papers, and paper pages without matching raw evidence.

### `/status`

Returns a vault health snapshot combining `lint_vault` output with directory counts (papers, concepts, ideas, conversations, raw evidence) and recent activity from `vault-log.md`. Agent-side; no new MCP tool required.
