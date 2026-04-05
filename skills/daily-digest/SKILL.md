---
name: daily-digest
description: Use when the user says "每日简报", "daily digest", "今天有什么新论文", "/digest", or wants the daily candidate discovery workflow.
---

# Daily Digest

Daily candidate discovery: search all configured topics, stage inbox candidates, generate a digest.

## Workflow

1. Read `settings.json → paper_distill.topics`
2. Call `query_vault(section="inbox")` and `query_vault(section="raw")` to get known paper IDs for deduplication
3. Invoke `paper-distill:paper-discover` for each configured topic
4. Create `daily-log/{YYYY-MM-DD}.md` following `templates/daily-log.md.j2` structure, including:
   - candidate count
   - top candidates by topic
   - venue and author signals
   - links to inbox notes
   - Dataview query for pending `status: proposed` papers (auto-updates in Obsidian)
5. Tell the user to approve or reject candidates in Obsidian by editing the `status` field

## Important

- Daily digest is a discovery and review workflow, not auto-ingest
- The Dataview query in the daily log renders dynamically — no need to manually update the list
