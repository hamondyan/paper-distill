# Stateless Discovery Design

## Context

Paper Distill currently treats discovery as the first step of an inbox-backed workflow:

```text
/discover -> inbox stubs -> /approve -> /ingest approved -> raw evidence
```

The new product direction removes `/inbox` from the user workflow. Search results should be shown once in the agent conversation. The user should not inspect `inbox/`, and discovery should not create hidden approval state.

## Decision

Use a fully stateless discovery model.

`/discover` searches configured paper sources, scores and ranks the returned papers, and returns those candidates directly to the agent for chat presentation. It does not write `inbox/*.md`, does not write a candidate cache, and does not mark papers as seen merely because they appeared in search results.

Direct capture remains the ingestion path:

```text
/discover -> agent presents candidates in chat
/ingest <arxiv-url|arxiv-id|arxiv-doi> -> raw evidence
```

The agent may help the user choose from the displayed results, but once the turn is over there is no persisted candidate list to approve.

## User-Facing Behavior

- `/discover [query]` returns a ranked list of search candidates with enough metadata for the agent to present them: paper ID, title, score, source URL, abstract or short summary when available, venue, year, and authors when available.
- `/discover` does not report saved inbox paths or saved counts.
- `/approve` no longer represents a useful workflow command. It should fail clearly or be retired from docs and command surfaces.
- `/ingest approved` no longer scans approved inbox notes. It should return a clear error telling the agent to pass resolved arXiv identities or URLs to `/ingest`.
- `/ingest <resolved paper references>` keeps working.

## Data Model

Discovery results are transient return values only.

The vault layout no longer includes `inbox/` as a required directory. `.state/seen_papers.json` is no longer part of discovery semantics. If existing vaults still contain those paths, the runtime should tolerate them, but new bootstrap should not create `inbox/` or initialize a discovery-specific seen cache.

Raw evidence, canonical papers, concepts, ideas, conversations, QMD collections, and lint behavior outside inbox-specific checks stay unchanged.

## Code Changes

- Change `server/v3_discovery.py` so `discover_papers_v3` returns transient ranked candidates and does not write inbox stubs or seen-paper cache entries.
- Remove or isolate inbox-specific discovery helpers that only exist to render or inspect inbox notes.
- Change `server/v3_ingest.py` so the `approved` input no longer reads `inbox/`; return a clear unsupported-workflow error instead.
- Change `server/v3_bootstrap.py` and shell bootstrap scripts so new vaults do not create `inbox/` or initialize `.state/seen_papers.json`.
- Change health/status/lint code and command docs so they do not count, recommend, or report inbox pending/approved/stale state.
- Update skills, commands, README, architecture, vault-layout, configuration, and frontmatter docs to describe chat-only discovery and direct ingest.

## Testing

Add or update tests before implementation:

- `discover_papers_v3` returns ranked candidate metadata without creating `inbox/`.
- `discover_papers_v3` does not create or update `.state/seen_papers.json`.
- Re-running discovery can return the same source result because discovery is stateless.
- `ingest_and_read_v3("approved")` returns an explicit unsupported-workflow error.
- Bootstrap does not create `inbox/`.
- Lint/health/status no longer depends on inbox stale or approved-note behavior.
- Existing direct ingest tests continue to pass.

## Migration

No destructive migration is required. Existing vaults may keep old `inbox/` files, but current commands should stop reading or writing them. Documentation should describe `inbox/` as retired rather than a current user-facing layer.
