# Commands

Paper Distill v3.0 exposes a small command surface.

- `/discover` writes inbox stubs.
- `/inbox` summarizes pending and approved candidates.
- `/ingest approved` or `/ingest <url>` captures raw evidence.
- `/search` uses `kb_search`.
- `/get` uses `kb_get`.
- `/lint` runs v3 health checks.
- `/status` reports readiness and qmd state.

## Tool Mapping

- `/discover` -> `discover_papers`
- `/ingest` -> `ingest_and_read`
- `/search` -> `kb_search`
- `/get` -> `kb_get`
- `/lint` -> `lint_vault`
- `/status` -> `status`

Approval is file-native: add a plain `#approved` tag to the inbox note body before running `/ingest approved`.
