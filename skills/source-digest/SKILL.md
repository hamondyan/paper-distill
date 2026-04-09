---
name: source-digest
description: Use when the user says "每日简报", "daily digest", "拉取今日论文", "今天的推荐", "今天有什么新论文", "/digest", or wants to run the scheduled daily paper discovery and generate a digest for review. This is the batch daily workflow — for ad-hoc searches on a specific topic, use `source-discover`.
---

# Source Digest

Daily candidate discovery: search all configured topics, stage inbox candidates, generate a digest.

## Workflow

1. Read `settings.json → paper_distill.topics`
2. Call `query-library(section="inbox")` and `query-library(section="source_notes")` to get known paper IDs for deduplication
3. Invoke `paper-distill:source-discover` for each configured topic
4. Create `insights/digests/{YYYY-MM-DD}.md` following `templates/daily-log.md.j2` structure, including:
   - candidate count
   - top candidates by topic
   - venue and author signals
   - links to inbox notes
   - Dataview query for pending `status: proposed` papers (auto-updates in Obsidian)
5. Generate two optional insight sections (LLM-powered):
   - **Emerging Patterns**: Cross-paper methodological trends observed in today's batch
   - **Challenges to Existing Notes**: Conflicts or updates to existing vault knowledge surfaced by new candidates
6. Mention that `Paper Distill/index.md` and `Paper Distill/log.md` are the cross-day navigation surfaces for visible knowledge growth
7. Tell the user to approve or reject candidates in Obsidian by editing the `status` field

## Important

- Daily digest is a discovery and review workflow, not auto-ingest
- The Dataview query in the daily log renders dynamically — no need to manually update the list
