# Agent-Resolved Paper Intake Design

Date: 2026-04-18
Status: Implemented / archived

## Context

At design time, Paper Distill had a conservative intake boundary. The `paper-intake` skill routed direct capture only when the user provided an arXiv URL or arXiv DOI, and the `ingest_and_read` MCP tool rejected direct inputs that could not yield an arXiv ID.

This protects `raw/evidence/`, but it makes natural intake clumsy. Users often refer to papers by title, acronym, model name, project name, or a mixed list of several papers. Examples include `openvla`, `Attention Is All You Need`, and multi-line lists containing both aliases and arXiv links.

The desired change is not to turn the deterministic MCP server into a broad natural-language resolver. Instead, the agent should use its own judgment and search ability to resolve user-provided paper references into arXiv URLs, then call the single intake interface with those resolved URLs.

## Goals

- Keep one user-facing intake interface: `ingest_and_read`.
- Let the agent accept natural paper references, including titles, acronyms, aliases, project names, arXiv links, arXiv IDs, and arXiv DOI values.
- Let the agent handle multi-paper requests in one turn.
- Do not require a second confirmation when the agent believes it has identified the right arXiv paper.
- Keep raw evidence writes deterministic and arXiv-grounded.
- Return per-paper success and error details for batch ingest.

## Non-Goals

- The MCP server will not become a general web search or natural-language paper resolver.
- The MCP server will not ingest arbitrary publisher pages, Semantic Scholar pages, OpenReview pages, PDFs, or non-arXiv URLs as raw evidence.
- The server will not ask the user to disambiguate candidate papers. Agent-side disambiguation remains outside the MCP contract.
- The server will not write raw evidence unless an arXiv ID can be extracted from each item.

## Architecture

The boundary is:

```text
User natural input
  -> Agent resolves each paper reference to an arXiv URL / arXiv ID / arXiv DOI
  -> Agent calls ingest_and_read once with the resolved arXiv identities
  -> MCP captures arXiv-family HTML and writes raw evidence
```

The agent owns semantic interpretation. It can use model knowledge, user context, web search, arXiv search, or any available tool to decide that `openvla` means the OpenVLA paper. Once it has a canonical arXiv URL, it calls the MCP tool directly without asking for another confirmation.

The MCP server owns deterministic capture. It only accepts `approved` or arXiv-bound identifiers. It extracts arXiv IDs, fetches arXiv native HTML with ar5iv fallback through the existing capture path, writes Markdown raw evidence, and reports structured results.

## Interface

Keep the existing tool:

```python
async def ingest_and_read(input_value: str) -> dict[str, Any]
```

Extend the accepted `input_value` forms:

- `approved`
- a single arXiv URL, arXiv ID, or arXiv DOI
- multiple arXiv URLs, arXiv IDs, or arXiv DOI values in one string

Batch separators should support common agent output formats:

- newlines
- Markdown bullets
- numbered lists
- comma-separated values
- semicolon-separated values

Examples:

```text
https://arxiv.org/abs/2405.12213
```

```text
- https://arxiv.org/abs/2405.12213
- 1706.03762
- 10.48550/arxiv.2410.24164
```

```text
https://arxiv.org/abs/2405.12213; https://arxiv.org/abs/1706.03762
```

The tool should reject any batch item that does not contain an arXiv ID. Other valid items in the same batch should still be captured.

## Agent Skill Behavior

Update `skills/paper-intake/SKILL.md` so the skill tells the agent:

- If the user provides arXiv-bound identifiers, call `ingest_and_read` directly.
- If the user provides titles, acronyms, aliases, project names, or mixed natural references, resolve each item to an arXiv URL first.
- Once the agent has resolved an item to an arXiv URL, include it in a single batch call to `ingest_and_read`.
- Do not ask for second confirmation after resolving a paper reference.
- If the agent cannot find a credible arXiv URL for an item, report that item as unresolved and do not include it in the MCP call.
- For multi-paper requests, resolve as many items as possible, ingest the resolved arXiv items, and report unresolved items separately.

This keeps the agent flexible without expanding the server's trust boundary.

## Server Behavior

`ingest_and_read_v3` should keep the existing `approved` flow unchanged.

For non-`approved` input:

1. Split the input string into candidate identifier items.
2. Extract an arXiv ID from each item using existing arXiv parsing logic.
3. For each valid arXiv ID:
   - fetch canonical arXiv metadata with `fetch_arxiv_record`;
   - call the existing `_capture_raw_evidence`;
   - write or refresh the raw evidence Markdown file;
   - return `paper_id`, title, path, source URL, and captured Markdown.
4. For each invalid item:
   - return a structured error saying that the item must be agent-resolved to an arXiv URL, arXiv ID, or arXiv DOI before capture.
5. Continue processing the rest of the batch even if one item fails.

The response should remain backward-compatible for single-item success, but include batch-friendly fields:

```json
{
  "items": [
    {
      "input": "https://arxiv.org/abs/2405.12213",
      "paper_id": "arxiv:2405.12213",
      "title": "Example Paper",
      "path": "/vault/raw/evidence/example-paper--arxiv-2405.12213.md",
      "source_url": "https://arxiv.org/abs/2405.12213"
    }
  ],
  "errors": [
    {
      "input": "openvla",
      "error": "Item must be resolved to an arXiv URL, arXiv ID, or arXiv DOI before capture."
    }
  ],
  "captured_count": 1,
  "error_count": 1
}
```

Existing callers that read `items` and `errors` should continue to work.

## User Experience

The user can say:

```text
帮我注入 openvla, octo, diffusion policy
```

The agent resolves the names itself, then calls:

```text
ingest_and_read(input_value="
https://arxiv.org/abs/...
https://arxiv.org/abs/...
https://arxiv.org/abs/...
")
```

The final response should summarize:

- captured papers with paths;
- unresolved references, if any;
- failed captures, if any;
- the recommended QMD refresh command after write-heavy work.

## Error Handling

- Empty input returns `input_value is required`.
- `approved` keeps the current approved-inbox behavior.
- Invalid batch items are reported per item and do not stop the batch.
- Capture errors are reported per item with title, paper ID when available, and source URL.
- Duplicate arXiv IDs within the same batch should be skipped after the first occurrence or reported as duplicate without rewriting twice.
- Existing raw evidence files should keep the current refresh behavior.

## Testing

Add or update tests for:

- single direct arXiv URL still succeeds;
- single arXiv DOI still succeeds;
- bare arXiv ID succeeds;
- newline batch with multiple arXiv URLs succeeds;
- bullet-list batch succeeds;
- mixed valid and invalid batch returns captured items plus per-item errors;
- duplicate IDs in one batch do not capture twice;
- `approved` behavior remains unchanged;
- skill/docs no longer imply that users must provide only arXiv URLs or arXiv DOI values.

## Open Decisions

None. The chosen product behavior is that agent-side resolution does not require a second user confirmation. The MCP server remains arXiv-grounded and deterministic.
